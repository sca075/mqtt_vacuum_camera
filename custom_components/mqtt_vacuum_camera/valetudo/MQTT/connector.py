"""
Version: v2024.12.0
"""

import asyncio
import json
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.core import EventOrigin, HomeAssistant, callback
from isal import igzip, isal_zlib

from ...common import build_full_topic_set
from ...const import DECODED_TOPICS, NON_DECODED_TOPICS, CameraModes
from ...types import RoomStore
from ...valetudo.rand256.rrparser import RRMapParser

_LOGGER = logging.getLogger(__name__)

_QOS = 0


class ValetudoConnector:
    """Valetudo Camera MQTT Connector."""

    def __init__(self, mqtt_topic: str, hass: HomeAssistant, camera_shared):
        self._hass = hass
        self._mqtt_topic = mqtt_topic
        self._unsubscribe_handlers = []
        self._ignore_data = False
        self._rcv_topic = None
        self._payload = None
        self._img_payload = None
        self._mqtt_vac_stat = ""
        self._mqtt_segments = {}
        self._mqtt_vac_connect_state = "disconnected"
        self._mqtt_vac_battery_level = None
        self._mqtt_vac_err = None
        self._data_in = False
        self._do_it_once = True  # Rand256
        self._is_rrm = False  # Rand256
        self._rrm_json = None  # Rand256
        self._rrm_payload = None  # Rand256
        self._rrm_destinations = None  # Rand256
        self._mqtt_vac_re_stat = None  # Rand256
        self._rrm_data = RRMapParser()  # Rand256
        self._rrm_active_segments = []  # Rand256
        self.rrm_attributes = None  # Rand256
        self._file_name = camera_shared.file_name
        self._shared = camera_shared
        self._room_store = RoomStore()
        vacuum_identifier = self._mqtt_topic.split("/")[-1]
        self.mqtt_hass_vacuum = f"homeassistant/vacuum/{vacuum_identifier}/{vacuum_identifier}_vacuum/config"
        self.command_topic = (
            f"{self._mqtt_topic}/hass/{vacuum_identifier}_vacuum/command"
        )
        self.rrm_command = f"{self._mqtt_topic}/command"  # added for ValetudoRe
        self._pkohelrs_maploader_map = None
        self.pkohelrs_state = None

    async def update_data(self, process: bool = True):
        """
        Update the data from MQTT.
        If it is a Valetudo RE, it will request the destinations.
        When the data is available, it will process it if the camera isn't busy.
        It simply unzips the data and returns the JSON.
        """
        payload = self._img_payload if self._img_payload else self._rrm_payload
        data_type = "Hypfer" if self._img_payload else "Rand256"
        loop = asyncio.get_running_loop()
        if payload:
            if process:
                _LOGGER.debug(
                    f"{self._file_name}: Processing {data_type} data from MQTT."
                )
                if data_type == "Hypfer":
                    json_data = await loop.run_in_executor(
                        None, lambda: isal_zlib.decompress(payload).decode()
                    )
                    result = json.loads(json_data)
                elif (data_type == "Rand256") and (self._ignore_data is False):
                    payload_decompressed = await loop.run_in_executor(
                        None, lambda: igzip.decompress(payload)
                    )
                    self._rrm_json = self._rrm_data.parse_data(
                        payload=payload_decompressed, pixels=True
                    )
                    result = self._rrm_json
                else:
                    result = None
                self._is_rrm = bool(self._rrm_json)
                self._data_in = False
                _LOGGER.info(
                    f"{self._file_name}: Extraction of {data_type} JSON Complete."
                )
                return result, data_type
            else:
                _LOGGER.info(
                    f"No image data from {self._mqtt_topic},"
                    f"vacuum in {self._mqtt_vac_stat} status."
                )
                self._ignore_data = True
                self._data_in = False
                self._is_rrm = False
                return None, data_type

    async def async_get_pkohelrs_maploader_map(self) -> str:
        """Return the Loaded Map of Dreame vacuums"""
        if self._pkohelrs_maploader_map:
            return self._pkohelrs_maploader_map
        return "No Maps Loaded"

    async def get_vacuum_status(self) -> str:
        """Return the vacuum status."""
        if (self._mqtt_vac_stat == "error") or (self._mqtt_vac_re_stat == "error"):
            # Fire the valetudo_error event when an error is detected
            self._hass.bus.async_fire(
                "valetudo_error",
                {"entity_id": f"vacuum.{self._file_name}", "error": self._mqtt_vac_err},
                EventOrigin.local,
            )
            return "error"
        if self._mqtt_vac_stat:
            return str(self._mqtt_vac_stat)
        if self._mqtt_vac_re_stat:
            return str(self._mqtt_vac_re_stat)

    async def get_vacuum_error(self) -> str:
        """Return the vacuum error."""
        return str(self._mqtt_vac_err)

    async def get_battery_level(self) -> str:
        """Rerun vacuum battery Level."""
        return str(self._mqtt_vac_battery_level)

    async def get_vacuum_connection_state(self) -> bool:
        """Return the vacuum connection state."""
        if self._mqtt_vac_connect_state != "ready":
            return False
        return True

    async def get_destinations(self) -> any:
        """Return the destinations used only for Rand256."""
        return self._rrm_destinations

    async def get_rand256_active_segments(self) -> list:
        """Return the active segments used only for Rand256."""
        return list(self._rrm_active_segments)

    async def is_data_available(self) -> bool:
        """Check and Return the data availability."""
        return bool(self._data_in)

    async def get_rand256_attributes(self):
        """If available return the vacuum attributes"""
        if bool(self.rrm_attributes):
            return self.rrm_attributes
        return {}

    async def handle_pkohelrs_maploader_map(self, msg) -> None:
        """Handle Pkohelrs Maploader current map loaded payload"""
        self._pkohelrs_maploader_map = await self.async_decode_mqtt_payload(msg)
        _LOGGER.debug(f"{self._file_name}: Loaded Map {self._pkohelrs_maploader_map}.")

    async def handle_pkohelrs_maploader_state(self, msg) -> None:
        """Get the pkohelrs state and handle camera restart"""
        new_state = await self.async_decode_mqtt_payload(msg)
        _LOGGER.debug(f"{self._file_name}: {self.pkohelrs_state} -> {new_state}")
        if (self.pkohelrs_state == "loading_map") and (new_state == "idle"):
            await self.async_fire_event_restart_camera(data=str(msg.payload))
        self.pkohelrs_state = new_state

    async def hypfer_handle_image_data(self, msg) -> None:
        """
        Handle new MQTT messages.
        MapData/map_data is for Hypfer.
        @param msg: MQTT message
        """
        if not self._data_in:
            _LOGGER.info(f"Received Hypfer {self._file_name} image data from MQTT")
            self._img_payload = msg.payload
            self._data_in = True

    async def hypfer_handle_status_payload(self, state) -> None:
        """
        Handle new MQTT messages.
        /StatusStateAttribute/status is for Hypfer.
        """
        if state:
            self._mqtt_vac_stat = state
            if self._mqtt_vac_stat != "docked":
                self._ignore_data = False

    async def hypfer_handle_connect_state(self, connect_state) -> None:
        """
        Handle new MQTT messages.
        /$state is for Hypfer.
        """
        if connect_state:
            self._mqtt_vac_connect_state = connect_state
        await self.is_disconnect_vacuum()

    async def is_disconnect_vacuum(self) -> None:
        """
        Disconnect the vacuum detected.
        Generate a Warning message if the vacuum is disconnected.
        """
        if (
            self._mqtt_vac_connect_state == "disconnected"
            or self._mqtt_vac_connect_state == "lost"
        ):
            _LOGGER.debug(
                f"{self._mqtt_topic}: Vacuum Disconnected from MQTT, waiting for connection."
            )
            self._mqtt_vac_stat = "disconnected"
            self._ignore_data = False
            if self._img_payload:
                self._data_in = True
        else:
            pass

    async def hypfer_handle_errors(self, errors) -> None:
        """
        Handle new MQTT messages.
        /StatusStateAttribute/error_description is for Hypfer.
        """
        self._mqtt_vac_err = errors
        _LOGGER.info(f"{self._mqtt_topic}: Received vacuum Error: {self._mqtt_vac_err}")

    async def hypfer_handle_battery_level(self, battery_state) -> None:
        """
        Handle new MQTT messages.
        /BatteryStateAttribute/level is for Hypfer.
        """
        if battery_state:
            self._mqtt_vac_battery_level = int(battery_state)

    async def hypfer_handle_map_segments(self, msg):
        """
        Handle incoming MQTT messages for the /MapData/segments topic.
        Decode the MQTT payload and store the segments in RoomStore.
        """
        self._mqtt_segments = await self.async_decode_mqtt_payload(msg)
        # Store the decoded segments in RoomStore
        await self._room_store.async_set_rooms_data(
            self._file_name, self._mqtt_segments
        )

    async def rand256_handle_image_payload(self, msg):
        """
        Handle new MQTT messages.
        map-data is for Rand256.
        """
        _LOGGER.info(f"Received Rand256 {self._file_name} image data from MQTT")
        # RRM Image data update the received payload
        self._rrm_payload = msg.payload
        if self._mqtt_vac_connect_state == "disconnected":
            self._mqtt_vac_connect_state = "ready"
        self._data_in = True
        self._ignore_data = False
        if self._do_it_once:
            #  Request the destinations from ValetudoRe.
            await self.publish_to_broker(
                f"{self._mqtt_topic}/custom_command", {"command": "get_destinations"}
            )
            self._do_it_once = False

    async def rand256_handle_statuses(self, msg) -> None:
        """
        Handle new MQTT messages.
        /state of ValetudoRe.
        @param msg: MQTT message
        """
        self._payload = msg.payload
        if self._payload:
            tmp_data = json.loads(self._payload)
            self._mqtt_vac_re_stat = tmp_data.get("state", None)
            self._mqtt_vac_battery_level = tmp_data.get("battery_level", None)
            if (
                self._mqtt_vac_stat != "docked"
                or int(self._mqtt_vac_battery_level) <= 100
            ):
                self._data_in = True
                self._is_rrm = True

    async def rand256_handle_destinations(self, msg) -> None:
        """
        Handle new MQTT messages.
        /destinations is for Rand256.
        @param msg: MQTT message
        """
        self._payload = msg.payload
        tmp_data = await self.async_decode_mqtt_payload(msg)
        self._rrm_destinations = tmp_data
        if "rooms" in tmp_data:
            rooms_data = {
                str(room["id"]): room["name"].strip("#") for room in tmp_data["rooms"]
            }
            await RoomStore().async_set_rooms_data(self._file_name, rooms_data)

    async def rrm_handle_active_segments(self, msg) -> None:
        """
        Handle new MQTT messages regarding active segments.
        /active_segments is for Rand256.
        """
        command_status = await self.async_decode_mqtt_payload(msg)
        command = command_status.get("command", None)

        if command == "segmented_cleanup":
            segment_ids = command_status.get("segment_ids", [])

            # Retrieve the shared room data instead of RoomStore or destinations
            shared_rooms_data = self._shared.map_rooms
            # Create a mapping of room ID to its index based on the shared rooms data
            room_id_to_index = {
                room_id: idx for idx, room_id in enumerate(shared_rooms_data)
            }

            # Initialize rrm_active_segments with zeros based on the number of rooms in shared_rooms_data
            rrm_active_segments = [0] * len(shared_rooms_data)

            # Update the rrm_active_segments based on segment_ids
            for segment_id in segment_ids:
                room_index = room_id_to_index.get(segment_id)
                if room_index is not None:
                    rrm_active_segments[room_index] = 1

            self._shared.rand256_active_zone = rrm_active_segments

    async def async_fire_event_restart_camera(
        self, event_text: str = "event_vacuum_start", data: str = ""
    ):
        """Fire Event to reset the camera trims"""
        self._hass.bus.async_fire(
            event_text,
            event_data={
                "device_id": f"mqtt_vacuum_{self._file_name}",
                "type": "mqtt_payload",
                "data": data,
            },
            origin=EventOrigin.local,
        )

    async def async_handle_start_command(self, msg):
        """fire event vacuum start"""
        if str(msg.payload).lower() == "start":
            # Fire the vacuum.start event when START command is detected
            await self.async_fire_event_restart_camera(data=str(msg.payload))

    @callback
    async def async_message_received(self, msg) -> None:
        """
        Handle new MQTT messages.
        MapData/map_data is for Hypfer, and map-data is for Rand256.

        """
        self._rcv_topic = msg.topic
        if self._shared.camera_mode == CameraModes.MAP_VIEW:
            if self._rcv_topic == f"{self._mqtt_topic}/map_data":
                await self.rand256_handle_image_payload(msg)
            elif (self._rcv_topic == f"{self._mqtt_topic}/MapData/map-data") and (
                not self._ignore_data
            ):
                await self.hypfer_handle_image_data(msg)
            elif self._rcv_topic == f"{self._mqtt_topic}/StatusStateAttribute/status":
                decoded_state = await self.async_decode_mqtt_payload(msg)
                await self.hypfer_handle_status_payload(decoded_state)
            elif self._rcv_topic == f"{self._mqtt_topic}/$state":
                decoded_connect_state = await self.async_decode_mqtt_payload(msg)
                await self.hypfer_handle_connect_state(decoded_connect_state)
            elif (
                self._rcv_topic
                == f"{self._mqtt_topic}/StatusStateAttribute/error_description"
            ):
                decode_errors = await self.async_decode_mqtt_payload(msg)
                await self.hypfer_handle_errors(decode_errors)
            elif self._rcv_topic == f"{self._mqtt_topic}/BatteryStateAttribute/level":
                decoded_battery_state = await self.async_decode_mqtt_payload(msg)
                await self.hypfer_handle_battery_level(decoded_battery_state)
            elif self._rcv_topic == f"{self._mqtt_topic}/state":
                await self.rand256_handle_statuses(msg)
            elif self._rcv_topic == f"{self._mqtt_topic}/custom_command":
                await self.rrm_handle_active_segments(msg)
            elif self._rcv_topic == f"{self._mqtt_topic}/destinations":
                await self._hass.async_create_task(
                    self.rand256_handle_destinations(msg)
                )
            elif self._rcv_topic == f"{self._mqtt_topic}/MapData/segments":
                await self.hypfer_handle_map_segments(msg)
            elif self._rcv_topic in [self.command_topic, self.rrm_command]:
                await self.async_handle_start_command(msg)
            elif self._rcv_topic == f"{self._mqtt_topic}/attributes":
                self.rrm_attributes = await self.async_decode_mqtt_payload(msg)
                try:
                    self._mqtt_vac_err = self.rrm_attributes.get(
                        "last_run_stats", {}
                    ).get("errorDescription", None)
                except AttributeError:
                    _LOGGER.debug("Error in getting last_run_stats")
            elif self._rcv_topic == f"{self._mqtt_topic}/maploader/map":
                await self.handle_pkohelrs_maploader_map(msg)
            elif self._rcv_topic == f"{self._mqtt_topic}/maploader/status":
                await self.handle_pkohelrs_maploader_state(msg)
            elif self._rcv_topic == self.mqtt_hass_vacuum:
                temp_json = await self.async_decode_mqtt_payload(msg)
                self._shared.vacuum_api = temp_json.get("device", {}).get(
                    "configuration_url", None
                )
                _LOGGER.debug(f"Vacuum API URL: {self._shared.vacuum_api}")
            elif (
                self._rcv_topic == f"{self._mqtt_topic}/WifiConfigurationCapability/ips"
            ):
                vacuum_host_ip = await self.async_decode_mqtt_payload(msg)
                # When IPV4 and IPV6 are available, use IPV4
                if vacuum_host_ip.split(",").__len__() > 1:
                    self._shared.vacuum_ips = vacuum_host_ip.split(",")[0]
                else:
                    # Use IPV4 when no IPV6 without split
                    self._shared.vacuum_ips = vacuum_host_ip
                _LOGGER.debug(f"Vacuum IPs: {self._shared.vacuum_ips}")

    async def async_subscribe_to_topics(self) -> None:
        """Subscribe to the MQTT topics for Hypfer and ValetudoRe."""
        if self._mqtt_topic:
            topics_with_none_encoding = build_full_topic_set(
                base_topic=self._mqtt_topic,
                topic_suffixes=NON_DECODED_TOPICS,
                add_topic=self.command_topic,
            )

            topics_with_default_encoding = build_full_topic_set(
                base_topic=self._mqtt_topic,
                topic_suffixes=DECODED_TOPICS,
                add_topic=self.rrm_command,
            )
            # add_topic=self.mqtt_hass_vacuum, for Hypfer config data.
            topics_with_default_encoding.add(self.mqtt_hass_vacuum)

            for x in topics_with_none_encoding:
                self._unsubscribe_handlers.append(
                    await mqtt.async_subscribe(
                        self._hass, x, self.async_message_received, _QOS, encoding=None
                    )
                )

            for x in topics_with_default_encoding:
                self._unsubscribe_handlers.append(
                    await mqtt.async_subscribe(
                        self._hass, x, self.async_message_received, _QOS
                    )
                )

    async def async_unsubscribe_from_topics(self) -> None:
        """Unsubscribe from all MQTT topics."""
        _LOGGER.debug("Unsubscribing topics!!!")
        map(lambda x: x(), self._unsubscribe_handlers)

    @staticmethod
    async def async_decode_mqtt_payload(msg) -> Any:
        """Decode the Vacuum payload."""

        def parse_string_payload(string_payload: str) -> Any:
            """Decode jsons or numbers float or int"""
            if string_payload.startswith("{") and string_payload.endswith("}"):
                try:
                    return json.loads(string_payload)
                except json.JSONDecodeError:
                    return string_payload

            if string_payload.isdigit() or string_payload.replace(".", "", 1).isdigit():
                try:
                    return (
                        float(string_payload)
                        if "." in string_payload
                        else int(string_payload)
                    )
                except ValueError:
                    pass

            return string_payload

        try:
            if isinstance(msg.payload, str):
                return parse_string_payload(msg.payload)
            elif isinstance(msg.payload, (int, float, bytes)):
                return msg.payload
            else:
                return msg.payload
        except ValueError as e:
            _LOGGER.warning(f"Value error during payload decoding: {e}")
            raise
        except TypeError as e:
            _LOGGER.warning(f"Type error during payload decoding: {e}")
            raise

    async def publish_to_broker(
        self, cust_topic: str, cust_payload: dict, retain: bool = False
    ) -> None:
        """
        Publish data to MQTT using the internal mqtt_topic prefix for custom topics
        """
        payload = json.dumps(cust_payload)
        await mqtt.async_publish(
            hass=self._hass,
            topic=cust_topic,
            payload=payload,
            qos=_QOS,
            retain=retain,
        )

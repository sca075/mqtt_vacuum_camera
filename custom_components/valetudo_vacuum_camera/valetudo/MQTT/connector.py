"""
Version: v2024.06.3
- Removed the PNG decode, the json is extracted from map-data instead of map-data-hass.
- Tested no influence on the camera performance.
- Added gzip library used in Valetudo RE data compression.
"""

import asyncio
import json
import logging

from homeassistant.components import mqtt
from homeassistant.core import callback
from homeassistant.helpers.storage import STORAGE_DIR
from isal import igzip, isal_zlib

from custom_components.valetudo_vacuum_camera.common import async_write_file_to_disk
from custom_components.valetudo_vacuum_camera.valetudo.rand256.rrparser import (
    RRMapParser,
)

_LOGGER = logging.getLogger(__name__)
_QOS = 0


class ValetudoConnector:
    """Valetudo Camera MQTT Connector."""

    def __init__(self, mqtt_topic, hass, camera_shared):
        self._hass = hass
        self._mqtt_topic = mqtt_topic
        self._unsubscribe_handlers = []
        self._ignore_data = False
        self._rcv_topic = None
        self._payload = None
        self._img_payload = None
        self._mqtt_vac_stat = ""
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
        self._file_name = camera_shared.file_name
        self._shared = camera_shared

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

    async def get_vacuum_status(self) -> str:
        """Return the vacuum status."""
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

    @callback
    async def save_payload(self, file_name: str) -> None:
        """
        Save payload when available.
        """
        if (self._img_payload and (self._data_in is True)) or (
            self._rrm_payload is not None
        ):
            file_data = b"No data"
            if self._img_payload:
                file_data = self._img_payload
            elif self._rrm_payload:
                file_data = self._rrm_payload
            await async_write_file_to_disk(
                file_to_write=f"{self._hass.config.path(STORAGE_DIR)}"
                f"/valetudo_camera/{file_name}.raw",
                data=file_data,
                is_binary=True,
            )
            _LOGGER.info(f"Saved image data from MQTT in {file_name}.raw!")

    async def hypfer_handle_image_data(self, msg) -> None:
        """
        Handle new MQTT messages.
        MapData/map_data is for Hypfer.
        @param msg: MQTT message
        """
        if not self._data_in:
            _LOGGER.info(f"Received {self._file_name} image data from MQTT")
            self._img_payload = msg.payload
            self._data_in = True

    async def hypfer_handle_status_payload(self, msg) -> None:
        """
        Handle new MQTT messages.
        /StatusStateAttribute/status" is for Hypfer.
        @param msg: MQTT message
        """
        self._payload = await self.async_decode_mqtt_payload(msg)
        if self._payload:
            self._mqtt_vac_stat = self._payload
            _LOGGER.info(
                f"{self._file_name}: Received vacuum {self._mqtt_vac_stat} status."
            )
            if self._mqtt_vac_stat != "docked":
                self._ignore_data = False

    async def hypfer_handle_connect_state(self, msg) -> None:
        """
        Handle new MQTT messages.
        /$state is for Hypfer.
        @param msg: MQTT message
        """
        self._payload = await self.async_decode_mqtt_payload(msg)
        if self._payload:
            self._mqtt_vac_connect_state = self._payload
            _LOGGER.info(
                f"{self._mqtt_topic}: Received vacuum connection status: {self._mqtt_vac_connect_state}."
            )
        await self.is_disconnect_vacuum()

    async def is_disconnect_vacuum(self) -> None:
        """
        Disconnect the vacuum detected.
        Generate a Warning message if the vacuum is disconnected.
        """
        if self._mqtt_vac_connect_state == "disconnected":
            _LOGGER.warning(
                f"{self._mqtt_topic}: Vacuum Disconnected from MQTT, waiting for connection."
            )
            self._mqtt_vac_stat = "disconnected"
            self._ignore_data = False
            if self._img_payload:
                self._data_in = True
        else:
            pass

    async def hypfer_handle_errors(self, msg) -> None:
        """
        Handle new MQTT messages.
        /StatusStateAttribute/error_description is for Hypfer.
        @param msg: MQTT message
        """
        self._payload = await self.async_decode_mqtt_payload(msg)
        self._mqtt_vac_err = self._payload
        _LOGGER.info(f"{self._mqtt_topic}: Received vacuum Error: {self._mqtt_vac_err}")

    async def hypfer_handle_battery_level(self, msg) -> None:
        """
        Handle new MQTT messages.
        /BatteryStateAttribute/level is for Hypfer.
        @param msg: MQTT message
        """
        self._payload = await self.async_decode_mqtt_payload(msg)
        if self._payload:
            self._mqtt_vac_battery_level = int(self._payload)
            _LOGGER.info(
                f"{self._file_name}: Received vacuum battery level: {self._mqtt_vac_battery_level}%."
            )

    async def rand256_handle_image_payload(self, msg):
        """
        Handle new MQTT messages.
        map-data is for Rand256.
        """
        _LOGGER.info(f"Received {self._file_name} image data from MQTT")
        # RRM Image data update the received payload
        self._rrm_payload = msg.payload
        if self._mqtt_vac_connect_state == "disconnected":
            self._mqtt_vac_connect_state = "ready"
        self._data_in = True
        self._ignore_data = False
        if self._do_it_once:
            _LOGGER.debug(f"Do it once.. request destinations to: {self._mqtt_topic}")
            await self.rrm_publish_destinations()
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
            _LOGGER.info(
                f"{self._file_name}: Received vacuum {self._mqtt_vac_re_stat} status "
                f"and battery level: {self._mqtt_vac_battery_level}%."
            )
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
        _LOGGER.info(
            f"{self._file_name}: Received vacuum destinations: {self._rrm_destinations}"
        )

    async def rrm_handle_active_segments(self, msg) -> None:
        """
        Handle new MQTT messages.
        /active_segments is for Rand256.
        @param msg: MQTT message
        { "command": "segmented_cleanup", "segment_ids": [2], "repeats": 1, "afterCleaning": "Base" }
        """
        command_status = json.loads(msg.payload)
        command = command_status.get("command", None)

        if command == "segmented_cleanup" and self._rrm_destinations:
            segment_ids = command_status.get("segment_ids", [])
            # Parse rooms JSON from _rrm_destinations
            rooms_json = json.loads(self._rrm_destinations)
            rooms = rooms_json.get("rooms", [])
            # Create a mapping of room IDs to their positions in rooms list
            room_ids = {room["id"]: idx for idx, room in enumerate(rooms, start=1)}
            # Initialize rrm_active_segments with zeros
            self._rrm_active_segments = [0] * len(rooms)

            for segment_id in segment_ids:
                if segment_id in room_ids:
                    room_idx = room_ids[segment_id] - 1  # Index start from 0
                    self._rrm_active_segments[room_idx] = 1
            self._shared.rand256_active_zone = self._rrm_active_segments
            _LOGGER.debug(
                f"Active Segments of {self._file_name}: {self._rrm_active_segments}"
            )

    @callback
    async def async_message_received(self, msg) -> None:
        """
        Handle new MQTT messages.
        MapData/map_data is for Hypfer, and map-data is for Rand256.
        """
        self._rcv_topic = msg.topic
        if self._rcv_topic == f"{self._mqtt_topic}/map_data":
            await self.rand256_handle_image_payload(msg)
        elif (self._rcv_topic == f"{self._mqtt_topic}/MapData/map-data") and (
            not self._ignore_data
        ):
            await self.hypfer_handle_image_data(msg)
        elif self._rcv_topic == f"{self._mqtt_topic}/StatusStateAttribute/status":
            await self.hypfer_handle_status_payload(msg)
        elif self._rcv_topic == f"{self._mqtt_topic}/$state":
            await self.hypfer_handle_connect_state(msg)
        elif (
            self._rcv_topic
            == f"{self._mqtt_topic}/StatusStateAttribute/error_description"
        ):
            await self.hypfer_handle_errors(msg)
        elif self._rcv_topic == f"{self._mqtt_topic}/BatteryStateAttribute/level":
            await self.hypfer_handle_battery_level(msg)
        elif self._rcv_topic == f"{self._mqtt_topic}/state":
            await self.rand256_handle_statuses(msg)
        elif self._rcv_topic == f"{self._mqtt_topic}/custom_command":
            await self.rrm_handle_active_segments(msg)
        elif self._rcv_topic == f"{self._mqtt_topic}/destinations":
            await self._hass.async_create_task(self.rand256_handle_destinations(msg))

    async def async_subscribe_to_topics(self) -> None:
        """Subscribe to the MQTT topics for Hypfer and ValetudoRe."""
        if self._mqtt_topic:
            for x in [
                f"{self._mqtt_topic}/MapData/map-data",
                f"{self._mqtt_topic}/StatusStateAttribute/status",
                f"{self._mqtt_topic}/StatusStateAttribute/error_description",
                f"{self._mqtt_topic}/$state",
                f"{self._mqtt_topic}/BatteryStateAttribute/level",
                f"{self._mqtt_topic}/map_data",  # added for ValetudoRe
                f"{self._mqtt_topic}/state",  # added for ValetudoRe
                f"{self._mqtt_topic}/destinations",  # added for ValetudoRe
                f"{self._mqtt_topic}/custom_command",  # added for ValetudoRe
            ]:
                self._unsubscribe_handlers.append(
                    await mqtt.async_subscribe(
                        self._hass, x, self.async_message_received, _QOS, encoding=None
                    )
                )

    async def rrm_publish_destinations(self) -> None:
        """
        Request the destinations from ValetudoRe.
        Destination is used to gater the room names.
        It also provides zones and points predefined in the ValetudoRe.
        """
        cust_payload = {"command": "get_destinations"}
        cust_payload = json.dumps(cust_payload)
        await mqtt.async_publish(
            self._hass,
            self._mqtt_topic + "/custom_command",
            cust_payload,
            _QOS,
            encoding="utf-8",
        )

    async def async_unsubscribe_from_topics(self) -> None:
        """Unsubscribe from all MQTT topics."""
        _LOGGER.debug("Unsubscribing topics!!!")
        map(lambda x: x(), self._unsubscribe_handlers)

    @staticmethod
    async def async_decode_mqtt_payload(msg):
        """Check if we need to decode or not the payload"""
        if isinstance(msg.payload, bytes):
            # If it's binary data, decode it
            payload_str = msg.payload.decode()
            return payload_str
        elif isinstance(msg.payload, (int, float)):
            # If it's a number, return it as is
            return msg.payload
        else:
            # If it's already a string or another type, return it as is
            return msg.payload

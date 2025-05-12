"""
Consolidated ValetudoConnector with grouped data.
Last Updated on version: 2025.3.0b2
"""

import asyncio
from dataclasses import dataclass, field
import json
from typing import Any, Dict, List

from homeassistant.components import mqtt
from homeassistant.core import EventOrigin, HomeAssistant, callback
from isal import igzip, isal_zlib  # pylint: disable=I1101
from valetudo_map_parser.config.rand25_parser import RRMapParser
from valetudo_map_parser.config.types import RoomStore

from custom_components.mqtt_vacuum_camera.common import (
    build_full_topic_set,
    redact_ip_filter,
)
from custom_components.mqtt_vacuum_camera.const import (
    DECODED_TOPICS,
    LOGGER,
    NON_DECODED_TOPICS,
    CameraModes,
)

_QOS = 0


# Data containers (each with ≤7 attributes)
@dataclass
class RRMData:
    """Class for RRM data."""

    rrm_json: Any = None
    rrm_payload: Any = None
    rrm_destinations: Any = None
    mqtt_vac_re_stat: Any = None
    rrm_active_segments: List[Any] = field(default_factory=list)
    rrm_attributes: Any = None
    rrm_command: str = ""


@dataclass
class MQTTData:
    """Class for MQTT data."""

    mqtt_vac_stat: str = ""
    mqtt_segments: Dict[Any, Any] = field(default_factory=dict)
    mqtt_vac_connect_state: str = "disconnected"
    mqtt_vac_battery_level: Any = None
    mqtt_vac_err: Any = None
    img_payload: Any = None


@dataclass
class PkohelrsData:
    """Class for Pkohelrs data."""

    maploader_map: Any = None
    state: Any = None


@dataclass
class ConnectorData:
    """Class for connector data."""

    hass: HomeAssistant
    unsubscribe_handlers: List[Any] = field(default_factory=list)
    ignore_data: bool = False
    rcv_topic: Any = None
    data_in: bool = False
    file_name: str = ""
    room_store: Any = None


@dataclass
class ConfigData:
    """Class for config data."""

    mqtt_topic: str
    command_topic: str
    mqtt_hass_vacuum: str
    is_rrm: bool = False
    do_it_once: bool = True
    shared: Any = None
    rrm_parser: Any = None


class ValetudoConnector:
    """
    Valetudo Camera MQTT Connector.
    """

    def __init__(
        self,
        mqtt_topic: str,
        hass: HomeAssistant,
        camera_shared: Any,
        is_rand256: bool = False,
    ):
        vacuum_identifier = mqtt_topic.split("/")[-1]
        command_topic = f"{mqtt_topic}/hass/{vacuum_identifier}_vacuum/command"
        mqtt_hass_vacuum = (
            f"homeassistant/vacuum/{vacuum_identifier}"
            f"/{vacuum_identifier}_vacuum/config"
        )

        self.config = ConfigData(
            mqtt_topic=mqtt_topic,
            command_topic=command_topic,
            mqtt_hass_vacuum=mqtt_hass_vacuum,
            shared=camera_shared,
            rrm_parser=RRMapParser(),
        )
        self.connector_data = ConnectorData(
            hass=hass,
            file_name=camera_shared.file_name,
            room_store=RoomStore(camera_shared.file_name),
        )
        self.is_rand256 = is_rand256
        self.mqtt_data = MQTTData()
        self.rrm_data = RRMData(rrm_command=f"{mqtt_topic}/command")
        self.pkohelrs_data = PkohelrsData()
        # Create a queue for decompression tasks
        self._decompression_queue = asyncio.Queue()
        # Start the background worker
        self._decompression_worker_task = asyncio.create_task(
            self._process_decompression_queue()
        )

    async def _process_decompression_queue(self):
        """
        Worker that continuously processes decompression tasks from the queue.
        Each task is a tuple (payload, data_type, future).
        """
        while True:
            payload, data_type, future = await self._decompression_queue.get()
            loop = asyncio.get_running_loop()
            try:
                if data_type == "Hypfer":
                    # Decompress using isal_zlib in an executor
                    json_data = await loop.run_in_executor(
                        None, lambda: isal_zlib.decompress(payload).decode()
                    )
                    result = json.loads(json_data)
                elif data_type == "Rand256" and not self.connector_data.ignore_data:
                    # Decompress using igzip in an executor
                    payload_decompressed = await loop.run_in_executor(
                        None, lambda: igzip.decompress(payload)
                    )
                    result = self.config.rrm_parser.parse_data(
                        payload=payload_decompressed, pixels=True
                    )
                    self.rrm_data.rrm_json = result
                else:
                    result = None
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
            finally:
                self._decompression_queue.task_done()

    async def update_data(self, process: bool = True):
        """
        Update the data from MQTT.
        Unzips the data and returns the JSON based on the data type.
        """
        payload = (
            self.rrm_data.rrm_payload if self.is_rand256 else self.mqtt_data.img_payload
        )
        data_type = "Rand256" if self.is_rand256 else "Hypfer"

        if payload and process:
            LOGGER.debug(
                "%s: Queuing %s data from MQTT for processing.",
                self.connector_data.file_name,
                data_type,
            )
            loop = asyncio.get_running_loop()
            # Create a Future to be fulfilled by the worker
            future = loop.create_future()
            # Enqueue the decompression task
            await self._decompression_queue.put((payload, data_type, future))
            # Await the result once the worker processes the task
            result = await future
            self.config.is_rrm = bool(self.rrm_data.rrm_json)
            self.connector_data.data_in = False
            LOGGER.info(
                "%s: Extraction of %s JSON Complete.",
                self.connector_data.file_name,
                data_type,
            )
            return result, data_type

        LOGGER.info(
            "%s: No image data from %s vacuum in %s status.",
            self.connector_data.file_name,
            self.config.mqtt_topic,
            self.mqtt_data.mqtt_vac_stat,
        )
        self.connector_data.ignore_data = True
        self.connector_data.data_in = False
        self.config.is_rrm = False
        return None, data_type

    async def get_vacuum_status(self) -> str | None:
        """Return the vacuum status."""
        if (self.mqtt_data.mqtt_vac_stat == "error") or (
            self.rrm_data.mqtt_vac_re_stat == "error"
        ):
            self.connector_data.hass.bus.async_fire(
                "valetudo_error",
                {
                    "entity_id": f"vacuum.{self.connector_data.file_name}",
                    "error": self.mqtt_data.mqtt_vac_err,
                },
                EventOrigin.local,
            )
            return "error"
        if self.mqtt_data.mqtt_vac_stat:
            return str(self.mqtt_data.mqtt_vac_stat)
        elif self.rrm_data.mqtt_vac_re_stat:
            return str(self.rrm_data.mqtt_vac_re_stat)
        return None

    async def get_vacuum_error(self) -> str:
        """Return the vacuum error."""
        return str(self.mqtt_data.mqtt_vac_err)

    async def get_battery_level(self) -> str:
        """Return vacuum battery level."""
        return str(self.mqtt_data.mqtt_vac_battery_level)

    async def get_vacuum_connection_state(self) -> bool:
        """Return the vacuum connection state."""
        return self.mqtt_data.mqtt_vac_connect_state == "ready"

    async def get_destinations(self) -> Any:
        """Return the destinations used only for Rand256."""
        return self.rrm_data.rrm_destinations

    async def get_rand256_active_segments(self) -> list:
        """Return the active segments used only for Rand256."""
        return list(self.rrm_data.rrm_active_segments)

    async def is_data_available(self) -> bool:
        """Check and return the data availability."""
        return bool(self.connector_data.data_in)

    async def get_rand256_attributes(self):
        """Return the vacuum attributes if available."""
        return self.rrm_data.rrm_attributes if self.rrm_data.rrm_attributes else {}

    async def _handle_pkohelrs_maploader_map(self, msg) -> None:
        """Handle Pkohelrs Maploader map payload."""
        self.pkohelrs_data.maploader_map = await self.async_decode_mqtt_payload(msg)
        LOGGER.debug(
            "%s: Loaded Map %r.",
            self.connector_data.file_name,
            self.pkohelrs_data.maploader_map,
        )

    async def _handle_pkohelrs_maploader_state(self, msg) -> None:
        """Handle Pkohelrs maploader state and possibly restart camera."""
        new_state = await self.async_decode_mqtt_payload(msg)
        LOGGER.debug(
            "%s: Pkohelrs state change: %s -> %s",
            self.connector_data.file_name,
            self.pkohelrs_data.state,
            new_state,
        )
        if self.pkohelrs_data.state == "loading_map" and new_state == "idle":
            await self.async_fire_event_restart_camera(data=str(msg.payload))
        self.pkohelrs_data.state = new_state

    async def _validate_compressed_header(
        self, payload: bytes, compression_type: str
    ) -> bool:
        """
        Validate compressed data headers and checksums.
        Args:
            payload: The compressed payload
            compression_type: Either "isal-zlib" or "gzip"
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            if len(payload) < 4:
                LOGGER.warning(
                    "%s Payload too short: %r",
                    self.connector_data.file_name,
                    payload[:10],
                )
                return False

            if compression_type == "isal-zlib":
                # isal-zlib header magic bytes: 0x78 0x9c
                if not payload.startswith(b"\x78\x9c"):
                    LOGGER.warning(
                        "%s Invalid isal-zlib header: %r",
                        self.connector_data.file_name,
                        payload[:10],
                    )
                    return False
                # Validate zlib header checksum
                if (payload[0] * 256 + payload[1]) % 31 != 0:
                    LOGGER.warning(
                        "%s Invalid isal-zlib header checksum",
                        self.connector_data.file_name,
                    )
                    return False
            elif compression_type == "gzip":
                # gzip header magic bytes: 0x1f 0x8b
                if not payload.startswith(b"\x1f\x8b"):
                    LOGGER.warning(
                        "%s Invalid gzip header: %r",
                        self.connector_data.file_name,
                        payload[:10],
                    )
                    return False

            return True

        except Exception as e:
            LOGGER.error(
                "%s Error validating %s payload: %s",
                self.connector_data.file_name,
                compression_type,
                str(e),
            )
            return False

    async def _hypfer_handle_image_data(self, msg) -> None:
        """Handle new Hypfer image data."""
        if not self.connector_data.data_in:
            LOGGER.info(
                "%s: Received Hypfer image data from MQTT",
                self.connector_data.file_name,
            )
            if await self._validate_compressed_header(msg.payload, "isal-zlib"):
                self.mqtt_data.img_payload = msg.payload
                self.connector_data.data_in = True
            else:
                self.connector_data.data_in = False

    async def _hypfer_handle_status_payload(self, state) -> None:
        """Handle Hypfer status payload."""
        if state:
            self.mqtt_data.mqtt_vac_stat = state
            if self.mqtt_data.mqtt_vac_stat != "docked":
                self.connector_data.ignore_data = False

    async def _hypfer_handle_connect_state(self, connect_state) -> None:
        """Handle Hypfer connect state."""
        if connect_state:
            self.mqtt_data.mqtt_vac_connect_state = connect_state
        await self.is_disconnect_vacuum()

    async def is_disconnect_vacuum(self) -> None:
        """Disconnect the vacuum if required."""
        if (
            "disconnected" in self.mqtt_data.mqtt_vac_connect_state
            or "lost" in self.mqtt_data.mqtt_vac_connect_state
        ):
            LOGGER.debug(
                "%s: Vacuum %s disconnected from MQTT, waiting for re-connection.",
                self.connector_data.file_name,
                self.config.mqtt_topic,
            )
            self.mqtt_data.mqtt_vac_stat = "disconnected"
            self.connector_data.ignore_data = False
            if self.mqtt_data.img_payload:
                self.connector_data.data_in = True

    async def _hypfer_handle_errors(self, errors) -> None:
        """Handle Hypfer errors."""
        self.mqtt_data.mqtt_vac_err = errors
        LOGGER.info(
            "%s: Received vacuum Error: %r",
            self.connector_data.file_name,
            self.mqtt_data.mqtt_vac_err,
        )

    async def _hypfer_handle_battery_level(self, battery_state) -> None:
        """Handle Hypfer battery level."""
        if battery_state:
            self.mqtt_data.mqtt_vac_battery_level = int(battery_state)

    async def _hypfer_handle_map_segments(self, msg) -> None:
        """Handle MQTT message for map segments."""
        self.mqtt_data.mqtt_segments = await self.async_decode_mqtt_payload(msg)
        self.connector_data.room_store.set_rooms(self.mqtt_data.mqtt_segments)

    async def _rand256_handle_image_payload(self, msg) -> None:
        """Handle Rand256 image payload."""
        LOGGER.info(
            "%s: Received Rand256 image data from MQTT",
            self.connector_data.file_name,
        )
        if await self._validate_compressed_header(msg.payload, "gzip"):
            self.rrm_data.rrm_payload = msg.payload
            if self.mqtt_data.mqtt_vac_connect_state == "disconnected":
                self.mqtt_data.mqtt_vac_connect_state = "ready"
            self.connector_data.data_in = True
            self.connector_data.ignore_data = False
            if self.config.do_it_once:
                await self.publish_to_broker(
                    f"{self.config.mqtt_topic}/custom_command",
                    {"command": "get_destinations"},
                )
                self.config.do_it_once = False
        else:
            self.connector_data.data_in = False

    async def rand256_handle_statuses(self, msg) -> None:
        """Handle Rand256 statuses."""
        temp_payload = msg.payload
        if temp_payload:
            tmp_data = json.loads(temp_payload)
            self.rrm_data.mqtt_vac_re_stat = tmp_data.get("state", None)
            self.mqtt_data.mqtt_vac_battery_level = tmp_data.get("battery_level", None)
            if (
                self.mqtt_data.mqtt_vac_stat != "docked"
                or int(self.mqtt_data.mqtt_vac_battery_level) <= 100
            ):
                self.connector_data.data_in = True
                self.config.is_rrm = True

    async def rand256_handle_destinations(self, msg) -> None:
        """Handle Rand256 destinations."""
        tmp_data = await self.async_decode_mqtt_payload(msg)
        self.rrm_data.rrm_destinations = tmp_data
        if "rooms" in tmp_data:
            rooms_data = {
                str(room["id"]): room["name"].strip("#") for room in tmp_data["rooms"]
            }
            self.connector_data.room_store.set_rooms(rooms_data)

    async def rrm_handle_active_segments(self, msg) -> None:
        """Handle Rand256 active segments."""
        command_status = await self.async_decode_mqtt_payload(msg)
        if command_status.get("command", None) == "segmented_cleanup":
            segment_ids = command_status.get("segment_ids", [])
            room_id_to_index = {
                room_id: idx for idx, room_id in enumerate(self.config.shared.map_rooms)
            }
            rrm_active_segments = [0] * len(self.config.shared.map_rooms)
            for segment_id in segment_ids:
                room_index = room_id_to_index.get(segment_id)
                if room_index is not None:
                    rrm_active_segments[room_index] = 1
            self.config.shared.rand256_active_zone = rrm_active_segments

    async def async_fire_event_restart_camera(
        self, event_text: str = "event_vacuum_start", data: str = ""
    ) -> None:
        """Fire event to restart the camera."""
        self.connector_data.hass.bus.async_fire(
            event_text,
            {
                "device_id": f"mqtt_vacuum_{self.connector_data.file_name}",
                "type": "mqtt_payload",
                "data": data,
            },
            EventOrigin.local,
        )

    async def async_handle_start_command(self, msg) -> None:
        """Handle start command."""
        if str(msg.payload).lower() == "start":
            await self.async_fire_event_restart_camera(data=str(msg.payload))

    @staticmethod
    async def async_decode_mqtt_payload(msg) -> Any:
        """Decode the Vacuum payload."""

        def parse_string_payload(string_payload: str) -> Any:
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
            if isinstance(msg.payload, (int, float, bytes)):
                return msg.payload
            return msg.payload
        except (ValueError, TypeError) as e:
            LOGGER.warning("Error during payload decoding: %r", e)
            raise

    async def publish_to_broker(
        self, cust_topic: str, cust_payload: dict, retain: bool = False
    ) -> None:
        """Publish data to MQTT using the internal mqtt_topic prefix for custom topics."""
        payload = json.dumps(cust_payload)
        await mqtt.async_publish(
            hass=self.connector_data.hass,
            topic=cust_topic,
            payload=payload,
            qos=_QOS,
            retain=retain,
        )

    async def async_subscribe_to_topics(self) -> None:
        """Subscribe to the MQTT topics for Hypfer and ValetudoRe."""
        if self.config.mqtt_topic:
            topics_with_none_encoding = build_full_topic_set(
                base_topic=self.config.mqtt_topic,
                topic_suffixes=NON_DECODED_TOPICS,
                add_topic=self.config.command_topic,
            )
            topics_with_default_encoding = build_full_topic_set(
                base_topic=self.config.mqtt_topic,
                topic_suffixes=DECODED_TOPICS,
                add_topic=self.rrm_data.rrm_command,
            )
            topics_with_default_encoding.add(self.config.mqtt_hass_vacuum)
            for topic in topics_with_none_encoding:
                self.connector_data.unsubscribe_handlers.append(
                    await mqtt.async_subscribe(
                        self.connector_data.hass,
                        topic,
                        self.async_message_received,
                        _QOS,
                        encoding=None,
                    )
                )
            for topic in topics_with_default_encoding:
                self.connector_data.unsubscribe_handlers.append(
                    await mqtt.async_subscribe(
                        self.connector_data.hass,
                        topic,
                        self.async_message_received,
                        _QOS,
                    )
                )

    async def async_unsubscribe_from_topics(self) -> None:
        """Unsubscribe from all MQTT topics."""
        LOGGER.debug("%s: Unsubscribing topics!!!", self.connector_data.file_name)
        for unsubscribe in self.connector_data.unsubscribe_handlers:
            unsubscribe()

    @redact_ip_filter
    def _log_vacuum_ips(self, ips: str) -> str:
        """Log vacuum IPs with redaction"""
        return f"{self.connector_data.file_name}: Vacuum IPs: {ips}"

    @callback
    async def async_message_received(self, msg) -> None:
        """
        Handle incoming MQTT messages using match-case to reduce branch complexity.
        This replaces the long if-elif chain.
        """
        self.connector_data.rcv_topic = msg.topic
        if self.config.shared.camera_mode != CameraModes.MAP_VIEW:
            return
        topic = self.connector_data.rcv_topic
        match topic:
            case t if t == f"{self.config.mqtt_topic}/map_data":
                await self._rand256_handle_image_payload(msg)
            case t if (
                t == f"{self.config.mqtt_topic}/MapData/map-data"
                and not self.connector_data.ignore_data
            ):
                await self._hypfer_handle_image_data(msg)
            case t if t == f"{self.config.mqtt_topic}/StatusStateAttribute/status":
                decoded_state = await self.async_decode_mqtt_payload(msg)
                await self._hypfer_handle_status_payload(decoded_state)
            case t if t == f"{self.config.mqtt_topic}/$state":
                decoded_connect_state = await self.async_decode_mqtt_payload(msg)
                await self._hypfer_handle_connect_state(decoded_connect_state)
            case t if (
                t == f"{self.config.mqtt_topic}/StatusStateAttribute/error_description"
            ):
                decode_errors = await self.async_decode_mqtt_payload(msg)
                await self._hypfer_handle_errors(decode_errors)
            case t if t == f"{self.config.mqtt_topic}/BatteryStateAttribute/level":
                decoded_battery_state = await self.async_decode_mqtt_payload(msg)
                await self._hypfer_handle_battery_level(decoded_battery_state)
            case t if t == f"{self.config.mqtt_topic}/state":
                await self.rand256_handle_statuses(msg)
            case t if t == f"{self.config.mqtt_topic}/custom_command":
                await self.rrm_handle_active_segments(msg)
            case t if t == f"{self.config.mqtt_topic}/destinations":
                await self.connector_data.hass.async_create_task(
                    self.rand256_handle_destinations(msg)
                )
            case t if t == f"{self.config.mqtt_topic}/MapData/segments":
                await self._hypfer_handle_map_segments(msg)
            case t if t in [self.config.command_topic, self.rrm_data.rrm_command]:
                await self.async_handle_start_command(msg)
            case t if t == f"{self.config.mqtt_topic}/attributes":
                self.rrm_data.rrm_attributes = await self.async_decode_mqtt_payload(msg)
                try:
                    self.mqtt_data.mqtt_vac_err = self.rrm_data.rrm_attributes.get(
                        "last_run_stats", {}
                    ).get("errorDescription", None)
                except AttributeError:
                    LOGGER.debug("Error in getting last_run_stats")
            case t if t == f"{self.config.mqtt_topic}/maploader/map":
                await self._handle_pkohelrs_maploader_map(msg)
            case t if t == f"{self.config.mqtt_topic}/maploader/status":
                await self._handle_pkohelrs_maploader_state(msg)
            case t if t == self.config.mqtt_hass_vacuum:
                temp_json = await self.async_decode_mqtt_payload(msg)
                self.config.shared.vacuum_api = temp_json.get("device", {}).get(
                    "configuration_url", None
                )
                LOGGER.debug(
                    "%s: Vacuum API URL: %s",
                    self.connector_data.file_name,
                    self.config.shared.vacuum_api,
                )
            case t if t == f"{self.config.mqtt_topic}/WifiConfigurationCapability/ips":
                vacuum_host_ip = await self.async_decode_mqtt_payload(msg)
                self.config.shared.vacuum_ips = (
                    vacuum_host_ip.split(",")[0]
                    if len(vacuum_host_ip.split(",")) > 1
                    else vacuum_host_ip
                )
                LOGGER.debug(self._log_vacuum_ips(self.config.shared.vacuum_ips))

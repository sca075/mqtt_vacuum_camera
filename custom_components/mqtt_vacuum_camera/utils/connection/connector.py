"""
Consolidated ValetudoConnector with grouped data.
Last Updated on version: 2025.10.0
"""

from collections.abc import Callable
from dataclasses import dataclass, field
import json
from typing import Any, Dict, List

from homeassistant.components import mqtt, persistent_notification
from homeassistant.core import EventOrigin, HomeAssistant, callback
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


def _str_to_bool(value: Any) -> bool:
    """
    Convert string or other value to boolean.
    Handles MQTT string boolean values like "true"/"false".

    Args:
        value: Value to convert (can be str, bool, int, etc.)

    Returns:
        bool: Converted boolean value
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "on", "yes")
    # For non-string, non-bool values (int, etc.), use truthiness
    return value != 0 if isinstance(value, (int, float)) else False


# Data containers (each with ≤7 attributes)
@dataclass
class RRMData:
    """Class for RRM data."""

    rrm_json: Any = None
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
    mop_attached: bool = False
    dustbin_attached: bool = False
    watertank_attached: bool = False
    operation_mode: str = ""
    water_usage: str = ""
    dock_status: str = ""
    valetudo_events: Dict[Any, Any] = field(default_factory=dict)


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
class ConnectorPayload:
    """Class for connector data."""

    processing_in_progress: bool = False
    previous_vacuum_state: str = ""


@dataclass
class ConfigData:
    """Class for config data."""

    mqtt_topic: str
    command_topic: str
    mqtt_hass_vacuum: str
    is_rrm: bool = False
    do_it_once: bool = True
    shared: Any = None


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
            is_rrm=is_rand256,
        )
        self.connector_data = ConnectorData(
            hass=hass,
            file_name=camera_shared.file_name,
            room_store=RoomStore(camera_shared.file_name),
            data_in=False,
            ignore_data=False,
        )
        self.connector_payload = ConnectorPayload()
        self.is_rand256 = is_rand256
        self.mqtt_data = MQTTData()
        self.rrm_data = RRMData(rrm_command=f"{mqtt_topic}/command")
        self.pkohelrs_data = PkohelrsData()
        self._notification_listeners: Dict[str, Callable[[], None]] = {}

    async def update_data(self, process: bool = True):
        """
        Update the data from MQTT.
        Unzips the data and returns the JSON based on the data type.
        """
        if not self.mqtt_data.img_payload:
            return None, None

        payload = self.mqtt_data.img_payload[0]
        data_type = self.mqtt_data.img_payload[1]
        if payload and process:
            # Await the result once the worker processes the task
            result = payload
            self.config.is_rrm = self.is_rand256
            self.connector_data.data_in = True
            return result, data_type

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
        if self.is_rand256 and self.rrm_data.mqtt_vac_re_stat:
            return str(self.rrm_data.mqtt_vac_re_stat).lower()
        return str(self.mqtt_data.mqtt_vac_stat).lower()

    async def get_vacuum_error(self) -> str:
        """Return the vacuum error."""
        return str(self.mqtt_data.mqtt_vac_err)

    async def get_battery_level(self) -> str:
        """Return vacuum battery level."""
        level = self.mqtt_data.mqtt_vac_battery_level
        # str(None) would return the literal string "None", which
        # valetudo_map_parser's vacuum_bat_charged() later feeds to int()
        # and crashes on. Fall back to 0 while no battery data is available
        # (e.g. the vacuum is offline) instead of propagating that string.
        return str(level) if level is not None else "0"

    async def get_vacuum_connection_state(self) -> bool:
        """Return the vacuum connection state."""
        self.config.shared.vacuum_connection = bool(
            self.mqtt_data.mqtt_vac_connect_state == "ready"
        )
        return self.config.shared.vacuum_connection

    def get_destinations(self) -> Any:
        """Return the destinations used only for Rand256."""
        return self.rrm_data.rrm_destinations

    async def get_rand256_active_segments(self) -> list:
        """Return the active segments used only for Rand256."""
        return list(self.rrm_data.rrm_active_segments)

    def is_data_available(self) -> bool:
        """Check and return the data availability."""
        return bool(self.connector_data.data_in)

    async def get_rand256_attributes(self):
        """Return the vacuum attributes if available."""
        return self.rrm_data.rrm_attributes if self.rrm_data.rrm_attributes else {}

    async def get_mop_attachment_status(self) -> bool:
        """Return mop attachment status."""
        return self.mqtt_data.mop_attached

    async def get_dustbin_attachment_status(self) -> bool:
        """Return dustbin attachment status."""
        return self.mqtt_data.dustbin_attached

    async def get_watertank_attachment_status(self) -> bool:
        """Return watertank attachment status."""
        return self.mqtt_data.watertank_attached

    async def get_operation_mode(self) -> str:
        """Return operation mode preset."""
        return self.mqtt_data.operation_mode

    async def get_water_usage(self) -> str:
        """Return water usage preset."""
        return self.mqtt_data.water_usage

    async def get_dock_status(self) -> str:
        """Return dock status."""
        return self.mqtt_data.dock_status

    async def get_valetudo_events(self) -> dict:
        """Return Valetudo events dictionary."""
        return self.mqtt_data.valetudo_events

    async def _handle_pkohelrs_maploader_map(self, msg) -> None:
        """Handle Pkohelrs Maploader map payload."""
        self.pkohelrs_data.maploader_map = await self._async_decode_mqtt_payload(msg)

    async def _handle_pkohelrs_maploader_state(self, msg) -> None:
        """Handle Pkohelrs maploader state and possibly restart camera."""
        new_state = await self._async_decode_mqtt_payload(msg)
        if self.pkohelrs_data.state == "loading_map" and new_state == "idle":
            await self.async_fire_event_restart_camera(data=str(msg.payload))
        self.pkohelrs_data.state = new_state

    async def _hypfer_handle_image_data(self, msg) -> None:
        """Handle new Hypfer image data."""
        self.mqtt_data.img_payload = [msg, "Hypfer"]
        self.connector_data.data_in = True
        self.connector_data.ignore_data = False

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
            self.mqtt_data.mqtt_vac_stat = "disconnected"
            self.connector_data.ignore_data = False
            if self.mqtt_data.img_payload:
                self.connector_data.data_in = True

    async def _hypfer_handle_errors(self, errors) -> None:
        """Handle Hypfer errors."""
        self.mqtt_data.mqtt_vac_err = errors

    async def _hypfer_handle_battery_level(self, battery_state) -> None:
        """Handle Hypfer battery level."""
        if battery_state:
            self.mqtt_data.mqtt_vac_battery_level = int(battery_state)

    async def _hypfer_handle_map_segments(self, msg) -> None:
        """Handle MQTT message for map segments."""
        self.mqtt_data.mqtt_segments = await self._async_decode_mqtt_payload(msg)
        self.connector_data.room_store.set_rooms(self.mqtt_data.mqtt_segments)

    async def _hypfer_handle_mop_attachment(self, mop_state) -> None:
        """Handle mop attachment state."""
        if mop_state is not None:
            self.mqtt_data.mop_attached = _str_to_bool(mop_state)
            # Update shared mop_mode based on both attachment and operation mode
            self.config.shared.mop_mode = (
                self.mqtt_data.mop_attached
                and "mop" in self.mqtt_data.operation_mode.lower()
            )

    async def _hypfer_handle_dustbin_attachment(self, dustbin_state) -> None:
        """Handle dustbin attachment state."""
        if dustbin_state is not None:
            self.mqtt_data.dustbin_attached = _str_to_bool(dustbin_state)

    async def _hypfer_handle_watertank_attachment(self, watertank_state) -> None:
        """Handle watertank attachment state."""
        if watertank_state is not None:
            self.mqtt_data.watertank_attached = _str_to_bool(watertank_state)
            # Update shared mop_mode - watertank implies mopping capability
            self.config.shared.mop_mode = (
                self.mqtt_data.watertank_attached
                and "mop" in self.mqtt_data.operation_mode.lower()
            )

    async def _hypfer_handle_operation_mode(self, mode) -> None:
        """Handle operation mode preset."""
        self.mqtt_data.operation_mode = str(mode)
        # Update shared mop_mode only if mop is attached AND mode contains "mop"
        self.config.shared.mop_mode = (
            self.mqtt_data.mop_attached and "mop" in str(mode).lower()
        )

    async def _hypfer_handle_water_usage(self, water_level) -> None:
        """Handle water usage preset."""
        self.mqtt_data.water_usage = str(water_level)

    async def _hypfer_handle_dock_status(self, status) -> None:
        """Handle dock status."""
        self.mqtt_data.dock_status = str(status)
        # Convert dock status to user-friendly text
        match str(status):
            case "emptying":
                dock_text = "Dustbin Emptying"
            case "cleaning":
                dock_text = "Cleaning Mop Pads"
            case "drying":
                dock_text = "Drying Mop Pads"
            case _:
                # idle, error, pause, and unknown values pass through as-is
                dock_text = str(status)
        self.config.shared.dock_state = dock_text

    async def _hypfer_handle_valetudo_events(self, events) -> None:
        """Handle Valetudo events (errors, warnings, etc.).

        Valetudo retains the events topic in MQTT. Each event has a 'processed'
        flag that Valetudo sets to True once the event has been acknowledged via
        any interface (its own web UI, the HTTP API, or the MQTT interact topic).
        'processed' does NOT mean a specific interface was used — it just means
        someone acknowledged it somewhere.

        Bidirectional sync:
        - Valetudo → HA: when an unprocessed event arrives, a persistent
          notification is created in HA and a state-change listener is registered
          so that dismissing the notification propagates back to Valetudo.
        - HA → Valetudo: when the user dismisses the HA notification,
          _dismiss_valetudo_event publishes to the MQTT interact topic, causing
          Valetudo to mark the event as processed and republish the events topic.
        - Valetudo → HA (reverse): when Valetudo republishes the event with
          processed=True (e.g. dismissed in the Valetudo web UI), the HA
          notification is dismissed automatically.
        """
        if events is None or not isinstance(events, dict):
            return
        self.mqtt_data.valetudo_events = events
        for event_id, event_data in events.items():
            if not isinstance(event_data, dict):
                continue
            event_class = event_data.get("__class", "")
            processed = event_data.get("processed", True)

            if event_class == "ErrorStateValetudoEvent":
                notification_id = f"valetudo_error_{event_id}"
                if processed:
                    # Event acknowledged (via any interface) — clear the HA notification.
                    # Unsubscribe BEFORE dismissing so our own dismiss call doesn't
                    # echo back through the REMOVED callback and re-publish the
                    # interact command Valetudo already processed.
                    self._unsubscribe_notification_listener(notification_id)
                    persistent_notification.async_dismiss(
                        self.connector_data.hass,
                        notification_id=notification_id,
                    )
                else:
                    error_message = event_data.get("message", "Unknown error")
                    self.mqtt_data.mqtt_vac_err = error_message
                    persistent_notification.async_create(
                        self.connector_data.hass,
                        message=f"**{self.connector_data.file_name}**\n\n{error_message}",
                        title="Valetudo Error",
                        notification_id=notification_id,
                    )
                    # Watch for the HA notification being dismissed so we can
                    # propagate the dismissal back to Valetudo.
                    self._register_notification_dismiss_listener(
                        event_id, "ok", notification_id
                    )

    def _unsubscribe_notification_listener(self, notification_id: str) -> None:
        """Remove and invoke a tracked persistent-notification callback, if any."""
        unsubscribe = self._notification_listeners.pop(notification_id, None)
        if unsubscribe is None:
            return
        unsubscribe()
        if unsubscribe in self.connector_data.unsubscribe_handlers:
            self.connector_data.unsubscribe_handlers.remove(unsubscribe)

    def _register_notification_dismiss_listener(
        self, event_id: str, interaction: str, notification_id: str
    ) -> None:
        """Register a dispatcher callback for persistent-notification removal.

        Persistent notifications stopped creating state machine entities in
        Home Assistant 2023.6, so tracking ``persistent_notification.<id>`` via
        ``async_track_state_change_event`` never fires. We use
        ``persistent_notification.async_register_callback`` and match on
        ``UpdateType.REMOVED`` + our ``notification_id`` instead.

        When the user dismisses the HA notification the callback schedules
        ``_dismiss_valetudo_event`` to publish the interact command, completing
        the HA → Valetudo direction of the bidirectional sync.

        Guards against duplicate registration: if a listener is already tracked
        for this notification_id, the call is a no-op.
        """
        if notification_id in self._notification_listeners:
            return

        @callback
        def _on_notification_update(
            update_type: persistent_notification.UpdateType,
            notifications: Dict[str, Any],
        ) -> None:
            if (
                update_type == persistent_notification.UpdateType.REMOVED
                and notification_id in notifications
            ):
                # Notification dismissed in HA — propagate back to Valetudo.
                self._unsubscribe_notification_listener(notification_id)
                self.connector_data.hass.async_create_task(
                    self._dismiss_valetudo_event(event_id, interaction)
                )

        unsub = persistent_notification.async_register_callback(
            self.connector_data.hass, _on_notification_update
        )
        self._notification_listeners[notification_id] = unsub
        self.connector_data.unsubscribe_handlers.append(unsub)

    async def _dismiss_valetudo_event(self, event_id: str, interaction: str) -> None:
        """Publish an interact command to Valetudo via MQTT to mark an event as processed.

        Valetudo's MQTT interact topic expects:
            {"id": "<event_id>", "interaction": "<interaction>"}

        The interaction value is event-class-specific:
            - ErrorStateValetudoEvent       → "ok"
            - ConsumableDepletedValetudoEvent → "reset"

        Source: ValetudoEventsNodeMqttHandle.js in the Valetudo backend.
        """
        topic = f"{self.config.mqtt_topic}/ValetudoEvents/valetudo_events/interact/set"
        await self.publish_to_broker(
            topic, {"id": event_id, "interaction": interaction}
        )
        LOGGER.debug(
            "%s: Sent dismiss for Valetudo event %s (interaction=%s)",
            self.connector_data.file_name,
            event_id,
            interaction,
        )

    async def _rand256_handle_image_payload(self, msg) -> None:
        """Handle Rand256 image payload."""
        self.mqtt_data.img_payload = [msg, "Rand256"]
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
        tmp_data = await self._async_decode_mqtt_payload(msg)
        self.rrm_data.rrm_destinations = tmp_data
        if "rooms" in tmp_data:
            rooms_data = {
                str(room["id"]): room["name"].strip("#") for room in tmp_data["rooms"]
            }
            self.connector_data.room_store.set_rooms(rooms_data)

    async def rrm_handle_active_segments(self, msg) -> None:
        """Handle Rand256 active segments."""
        command_status = await self._async_decode_mqtt_payload(msg)
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
    async def _async_decode_mqtt_payload(msg) -> Any:
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
        if ips:
            self.config.shared.vacuum_ips = ips
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
                decoded_state = await self._async_decode_mqtt_payload(msg)
                await self._hypfer_handle_status_payload(decoded_state)
            case t if t == f"{self.config.mqtt_topic}/$state":
                decoded_connect_state = await self._async_decode_mqtt_payload(msg)
                await self._hypfer_handle_connect_state(decoded_connect_state)
            case t if (
                t == f"{self.config.mqtt_topic}/StatusStateAttribute/error_description"
            ):
                decode_errors = await self._async_decode_mqtt_payload(msg)
                await self._hypfer_handle_errors(decode_errors)
            case t if t == f"{self.config.mqtt_topic}/BatteryStateAttribute/level":
                decoded_battery_state = await self._async_decode_mqtt_payload(msg)
                await self._hypfer_handle_battery_level(decoded_battery_state)
            case t if t == f"{self.config.mqtt_topic}/AttachmentStateAttribute/mop":
                decoded_mop_state = await self._async_decode_mqtt_payload(msg)
                await self._hypfer_handle_mop_attachment(decoded_mop_state)
            case t if t == f"{self.config.mqtt_topic}/AttachmentStateAttribute/dustbin":
                decoded_dustbin_state = await self._async_decode_mqtt_payload(msg)
                await self._hypfer_handle_dustbin_attachment(decoded_dustbin_state)
            case t if (
                t == f"{self.config.mqtt_topic}/AttachmentStateAttribute/watertank"
            ):
                decoded_watertank_state = await self._async_decode_mqtt_payload(msg)
                await self._hypfer_handle_watertank_attachment(decoded_watertank_state)
            case t if (
                t == f"{self.config.mqtt_topic}/OperationModeControlCapability/preset"
            ):
                decoded_operation_mode = await self._async_decode_mqtt_payload(msg)
                await self._hypfer_handle_operation_mode(decoded_operation_mode)
            case t if (
                t == f"{self.config.mqtt_topic}/WaterUsageControlCapability/preset"
            ):
                decoded_water_usage = await self._async_decode_mqtt_payload(msg)
                await self._hypfer_handle_water_usage(decoded_water_usage)
            case t if t == f"{self.config.mqtt_topic}/DockStatusStateAttribute/status":
                decoded_dock_status = await self._async_decode_mqtt_payload(msg)
                await self._hypfer_handle_dock_status(decoded_dock_status)
            case t if t == f"{self.config.mqtt_topic}/ValetudoEvents/valetudo_events":
                decoded_events = await self._async_decode_mqtt_payload(msg)
                await self._hypfer_handle_valetudo_events(decoded_events)
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
                self.rrm_data.rrm_attributes = await self._async_decode_mqtt_payload(
                    msg
                )
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
                temp_json = await self._async_decode_mqtt_payload(msg)
                if isinstance(temp_json, dict):
                    self.config.shared.vacuum_api = temp_json.get("device", {}).get(
                        "configuration_url", None
                    )
                elif isinstance(temp_json, str):
                    self.config.shared.vacuum_api = temp_json
                else:
                    self.config.shared.vacuum_api = None
                LOGGER.debug(
                    "%s: Vacuum API URL: %s",
                    self.connector_data.file_name,
                    self.config.shared.vacuum_api,
                )
            case t if t == f"{self.config.mqtt_topic}/WifiConfigurationCapability/ips":
                vacuum_host_ip = await self._async_decode_mqtt_payload(msg)
                self.config.shared.vacuum_ips = (
                    vacuum_host_ip.split(",")[0]
                    if len(vacuum_host_ip.split(",")) > 1
                    else vacuum_host_ip
                )
                LOGGER.debug(self._log_vacuum_ips(self.config.shared.vacuum_ips))

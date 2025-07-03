"""
MQTT Vacuum Camera Coordinator.
Version: 2025.3.0b0
"""

import asyncio
from datetime import timedelta
from typing import Optional, Any

import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from valetudo_map_parser.config.shared import CameraShared, CameraSharedManager

from .const import DEFAULT_NAME, SENSOR_NO_DATA, LOGGER
from .common import get_camera_device_info
from .utils.connection.connector import ValetudoConnector
from .utils.connection.decompress import DecompressionManager
from .utils.model import VacuumData, SensorData
from .utils.vacuum.vacuum_state import VacuumStateManager
from .utils.thread_pool import ThreadPoolManager
from .utils.camera.camera_processing import CameraProcessor


class SensorsCoordinator(DataUpdateCoordinator[VacuumData]):
    """Coordinator for MQTT Vacuum Camera."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        vacuum_topic: str,
        rand256_vacuum: bool = False,
        connector: Optional[ValetudoConnector] = None,
        shared: Optional[CameraShared] = None,
    ):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DEFAULT_NAME,
            update_method=self._async_update_data,
        )
        self.hass: HomeAssistant = hass
        self.vacuum_topic: str = vacuum_topic
        self.data = VacuumData["sensors"]
        self.is_rand256: bool = rand256_vacuum
        self.device_entity: ConfigEntry = entry
        self.device_info: DeviceInfo = get_camera_device_info(hass, self.device_entity)
        self.shared_manager: Optional[CameraSharedManager] = None
        self.shared: Optional[CameraShared] = None
        self.file_name: str = ""
        self.connector: Optional[ValetudoConnector] = None
        self.in_sync_with_camera: bool = False
        self.sensor_data = SENSOR_NO_DATA
        self.thread_pool = None
        # Initialize shared data and MQTT connector
        if shared:
            self.shared = shared
            self.file_name = shared.file_name
        else:
            self.shared, self.file_name = self._init_shared_data(self.vacuum_topic)
        if connector:
            self.connector = connector
        else:
            self.connector = self.start_up_mqtt()
        self.scheduled_refresh: asyncio.TimerHandle | None = None

    def schedule_refresh(self) -> None:
        """Schedule coordinator refresh after 1 second."""
        if self.scheduled_refresh:
            self.scheduled_refresh.cancel()
        self.scheduled_refresh = async_call_later(
            self.hass, 1, lambda: asyncio.create_task(self.async_refresh())
        )

    async def _async_update_data(self):
        """
        Fetch data from the MQTT topics for sensors.
        """
        if self.shared is not None and self.connector:
            try:
                async with async_timeout.timeout(10):
                    # Fetch and process sensor data from the MQTT connector
                    sensor_data = await self.connector.get_rand256_attributes()
                    if sensor_data:
                        # Format the data before returning it
                        self.sensor_data = await self.async_update_sensor_data(
                            sensor_data
                        )
                        return self.sensor_data
                    return self.sensor_data
            except Exception as err:
                LOGGER.error(
                    "Exception raised fetching sensor data: %s", err, exc_info=True
                )
                raise UpdateFailed(f"Error fetching sensor data: {err}") from err
        else:
            return self.sensor_data

    def _init_shared_data(
        self, mqtt_listen_topic: str
    ) -> tuple[Optional[CameraShared], Optional[str]]:
        """
        Initialize the shared data.
        """
        shared = None
        file_name = None

        if mqtt_listen_topic and not self.shared_manager:
            file_name = mqtt_listen_topic.split("/")[1].lower()
            self.shared_manager = CameraSharedManager(file_name, self.device_info)
            self.thread_pool = ThreadPoolManager(file_name)
            shared = self.shared_manager.get_instance()
            LOGGER.debug("Camera %s Starting up..", file_name)

        return shared, file_name

    def start_up_mqtt(self) -> ValetudoConnector:
        """
        Initialize the MQTT Connector.
        """
        self.connector = ValetudoConnector(
            self.vacuum_topic, self.hass, self.shared, self.is_rand256
        )
        return self.connector

    def update_shared_data(self, dev_info: DeviceInfo) -> tuple[CameraShared, str]:
        """
        Create or update the instance of the shared data.
        """
        self.shared_manager.update_shared_data(dev_info)
        self.shared = self.shared_manager.get_instance()
        self.shared.file_name = self.file_name
        self.shared.device_info = dev_info
        self.shared.is_rand = self.is_rand256
        self.in_sync_with_camera = True
        return self.shared, self.file_name

    async def async_update_sensor_data(self, sensor_data) -> SensorData:
        """Update the sensor data format before sending to the sensors."""
        try:
            if not sensor_data:
                return SENSOR_NO_DATA

            try:
                battery_level = await self.connector.get_battery_level()
                vacuum_state = await self.connector.get_vacuum_status()
            except (AttributeError, ConnectionError) as err:
                LOGGER.warning("Failed to get vacuum status: %s", err, exc_info=True)
                return SENSOR_NO_DATA

            vacuum_room = self.shared.current_room or {"in_room": "Unsupported"}
            last_run_stats = sensor_data.get("last_run_stats", {})
            last_loaded_map = sensor_data.get("last_loaded_map", {"name": "Default"})

            if last_run_stats is None:
                last_run_stats = {}
            if not last_loaded_map:
                last_loaded_map = {"name": "Default"}

            formatted_data = {
                "mainBrush": sensor_data.get("mainBrush", 0),
                "sideBrush": sensor_data.get("sideBrush", 0),
                "filter": sensor_data.get("filter", 0),
                "sensor": sensor_data.get("sensor", 0),
                "currentCleanTime": sensor_data.get("currentCleanTime", 0),
                "currentCleanArea": sensor_data.get("currentCleanArea", 0),
                "cleanTime": sensor_data.get("cleanTime", 0),
                "cleanArea": sensor_data.get("cleanArea", 0),
                "cleanCount": sensor_data.get("cleanCount", 0),
                "battery": battery_level,
                "state": vacuum_state,
                "last_run_start": last_run_stats.get("startTime", 0),
                "last_run_end": last_run_stats.get("endTime", 0),
                "last_run_duration": last_run_stats.get("duration", 0),
                "last_run_area": last_run_stats.get("area", 0),
                "last_bin_out": sensor_data.get("last_bin_out", 0),
                "last_bin_full": sensor_data.get("last_bin_full", 0),
                "last_loaded_map": last_loaded_map.get("name", "Default"),
                "robot_in_room": vacuum_room.get("in_room"),
            }
            return formatted_data

        except AttributeError as err:
            LOGGER.warning("Missing required attribute: %s", err, exc_info=True)
            return SENSOR_NO_DATA
        except KeyError as err:
            LOGGER.warning(
                "Missing required key in sensor data: %s", err, exc_info=True
            )
            return SENSOR_NO_DATA
        except TypeError as err:
            LOGGER.warning("Invalid data type in sensor data: %s", err, exc_info=True)
            return SENSOR_NO_DATA


class CameraCoordinator(DataUpdateCoordinator[VacuumData]):
    """Coordinator for MQTT Vacuum Camera."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        vacuum_topic: str,
        is_rand256: bool = False,
        connector: Optional[ValetudoConnector] = None,
        shared: Optional[CameraShared] = None,
    ) -> None:
        """Initialize the camera coordinator - keep it simple."""

        # Basic setup first
        self.vacuum_topic = vacuum_topic
        self.is_rand256 = is_rand256
        self.file_name = vacuum_topic.split("/")[1].lower()
        self._prev_image = None
        self._prev_data_type = None
        self.device_entity: ConfigEntry = entry
        self.device_info: DeviceInfo = get_camera_device_info(hass, self.device_entity)
        # Initialize shared data (from working code pattern)
        if shared:
            self.shared = shared
        else:
            self.shared_manager = CameraSharedManager(self.file_name, self.device_info)
            self.shared = self.shared_manager.get_instance()
            self.shared.file_name = self.file_name
            self.shared.user_language = "en"  # Set default language
            self.shared.is_rand = is_rand256
            self.shared.vacuum_state = "disconnected"

        # Initialize thread pools (keep existing stable code)
        self.thread_pool = ThreadPoolManager(self.file_name)

        # Initialize connector (from working code)
        if connector:
            self.connector = connector
        else:
            self.connector = ValetudoConnector(vacuum_topic, hass, self.shared, is_rand256)

        # Initialize decompression (from working code)
        self.decompression_manager = DecompressionManager.get_instance(self.file_name)

        # Initialize camera processor (for JSON to PIL processing)
        self.processor = CameraProcessor(hass, self.shared)
        # Initialize vacuum state manager (add after connector is created)
        self.state_manager = VacuumStateManager(
            shared_data=self.shared, connector=self.connector, file_name=self.file_name
        )

        # Coordinator init
        super().__init__(
            hass,
            LOGGER,
            name=f"MQTT Vacuum Camera {vacuum_topic}",
            update_interval=timedelta(seconds=2),
            update_method=self.update_data,
        )

        # Mark as ready
        self._setup_complete = True
        self._mqtt_subscribed = False
        self.async_request_refresh()

        LOGGER.debug("Camera coordinator initialized for: %s", self.file_name)

    @property
    def setup_complete(self) -> bool:
        """Return True if coordinator setup is complete."""
        return self._setup_complete

    async def update_data(self) -> dict[str, Any]:
        """Process MQTT data to PIL image - coordinator handles all processing."""
        should_stream = await self.state_manager.update_vacuum_state()
        try:
            # Check if data is available (from working code)
            if await self.connector.is_data_available():
                LOGGER.debug("MQTT data available for: %s", self.file_name)
                payload, data_type = await self.connector.update_data(True)
                if payload and data_type:
                    # Decompress the data
                    data = payload.payload if hasattr(payload, "payload") else payload
                    parsed_json = await self.decompression_manager.decompress(
                        data, data_type
                    )

                    if parsed_json:
                        LOGGER.debug("JSON decompressed for: %s", self.file_name)

                        # Process JSON to PIL image
                        pil_img = await self.processor.run_async_process_valetudo_data(
                            parsed_json
                        )
                        if pil_img:
                            LOGGER.debug("PIL image processed for: %s", self.file_name)

                            # Cache for next time when no new data
                            self._prev_image = pil_img
                            self._prev_data_type = data_type

                            # Return NEW processed data
                            return {
                                "pil_image": pil_img,
                                "shared_data": self.shared,
                                "thread_pool": self.thread_pool,
                                "data_type": data_type,
                                "vacuum_topic": self.vacuum_topic,
                                "parsed_json": parsed_json,
                                "segments": parsed_json.get("segments", {}),
                                "vacuum_status": self.shared.vacuum_state,
                                "vacuum_battery": self.shared.vacuum_battery,
                                "vacuum_connection": True,
                                "image_width": pil_img.width,
                                "image_height": pil_img.height,
                                "success": should_stream,
                            }
                        else:
                            LOGGER.warning(
                                "Failed to process JSON to PIL for: %s", self.file_name
                            )
                    else:
                        LOGGER.warning(
                            "Failed to decompress data for: %s", self.file_name
                        )

            # Return previous image data
            if self._prev_image:
                return {
                    "pil_image": self._prev_image,
                    "shared_data": self.shared,
                    "thread_pool": self.thread_pool,
                    "data_type": self._prev_data_type,
                    "vacuum_topic": self.vacuum_topic,
                    "vacuum_status": self.shared.vacuum_state,
                    "vacuum_battery": self.shared.vacuum_battery,
                    "vacuum_connection": True,
                    "success": should_stream,
                }
            else:
                # No previous image available
                return {
                    "shared_data": self.shared,
                    "thread_pool": self.thread_pool,
                    "vacuum_topic": self.vacuum_topic,
                    "vacuum_status": self.shared.vacuum_state,
                    "vacuum_battery": self.shared.vacuum_battery,
                    "vacuum_connection": True,
                    "success": should_stream,
                }

        except Exception as err:
            LOGGER.error("Error processing image for %s: %s", self.file_name, err)
            # Return error data
            return {
                "shared_data": self.shared,
                "thread_pool": self.thread_pool,
                "vacuum_topic": self.vacuum_topic,
                "error_message": str(err),
                "success": False,
            }

    async def async_subscribe_mqtt(self) -> None:
        """Subscribe to MQTT topics."""
        if self._mqtt_subscribed:
            return

        try:
            LOGGER.debug("Subscribing to MQTT topics for: %s", self.file_name)
            await self.connector.async_subscribe_to_topics()
            self._mqtt_subscribed = True
            LOGGER.debug("MQTT subscription complete for: %s", self.file_name)
        except Exception as err:
            LOGGER.error("Failed to subscribe to MQTT for %s: %s", self.file_name, err)
            raise

    async def async_unsubscribe_mqtt(self) -> None:
        """Unsubscribe from MQTT topics."""
        if not self._mqtt_subscribed:
            return

        try:
            LOGGER.debug("Unsubscribing from MQTT topics for: %s", self.file_name)
            await self.connector.async_unsubscribe_from_topics()
            self._mqtt_subscribed = False
            LOGGER.debug("MQTT unsubscription complete for: %s", self.file_name)
        except Exception as err:
            LOGGER.error(
                "Failed to unsubscribe from MQTT for %s: %s", self.file_name, err
            )

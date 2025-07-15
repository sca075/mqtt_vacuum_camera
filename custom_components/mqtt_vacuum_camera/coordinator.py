"""
MQTT Vacuum Camera Coordinator.
Version: 2025.7.0
"""

import asyncio
from typing import Optional, Dict, Any
from PIL import Image

import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from valetudo_map_parser.config.shared import CameraShared, CameraSharedManager
from valetudo_map_parser.config.types import DEFAULT_IMAGE_SIZE

from .const import DOMAIN, DEFAULT_NAME, SENSOR_NO_DATA, LOGGER
from .common import get_camera_device_info
from .utils.connection.connector import ValetudoConnector
from .utils.connection.decompress import DecompressionManager
from .utils.model import VacuumData, SensorData, CameraImageData
from .utils.vacuum.vacuum_state import VacuumStateManager
from .utils.thread_pool import ThreadPoolManager, TaskQueue
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
        self.is_rand256: bool = rand256_vacuum
        self.device_entity: ConfigEntry = entry
        self.device_info: DeviceInfo = get_camera_device_info(hass, self.device_entity)
        self.shared_manager: Optional[CameraSharedManager] = None
        self.shared: Optional[CameraShared] = None
        self.file_name: str = ""
        self.connector: Optional[ValetudoConnector] = None
        self.in_sync_with_camera: bool = False
        self.sensor_data = SENSOR_NO_DATA
        # Initialize shared data and MQTT connector
        if shared:
            self.shared = shared
            self.file_name = shared.file_name
        if connector:
            self.connector = connector
        self.scheduled_refresh: asyncio.TimerHandle | None = None

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

    async def async_update_sensor_data(self, sensor_data) -> Dict[str, Any]:
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
                "filter_life": sensor_data.get("filter", 0),
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
            return SensorData(**formatted_data).to_dict()

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
        self.current_image = None
        self._prev_image = None
        self._prev_data_type = None
        self.device_entity: ConfigEntry = entry
        self.device_info: DeviceInfo = get_camera_device_info(hass, self.device_entity)
        self.task_async = TaskQueue()
        # Initialize shared data (from working code pattern)
        if shared:
            self.shared = shared
            self.shared.file_name = self.file_name
            self.shared.user_language = "en"  # Set default language
            self.shared.is_rand = is_rand256
            self.shared.vacuum_state = "disconnected"

        self._unsub_dispatcher = async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{self.file_name}_camera_update",
            self._handle_mqtt_camera_event,
        )

        # Initialize thread pools (keep existing stable code)
        self.thread_pool = ThreadPoolManager(self.file_name)

        # Initialize connector (from working code)
        if connector:
            self.connector = connector
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
            name=f"MQTT Vacuum Camera {self.file_name}",
            update_interval=None,
            always_update=False,
            update_method=self._handle_mqtt_camera_event,
        )

        # Mark as ready
        self._first_update = True
        self.actual_data_type = None
        self._setup_complete = True
        self._mqtt_subscribed = False

        LOGGER.debug("Camera coordinator initialized for: %s", self.file_name)

    @property
    def setup_complete(self) -> bool:
        """Return True if coordinator setup is complete."""
        return self._setup_complete

    async def async_process_image(self):
        """Process the parsed JSON data to a PIL image."""
        payload, self.actual_data_type = await self.connector.update_data(True)
        if payload and self.actual_data_type:
            data = payload.payload if hasattr(payload, "payload") else payload
            parsed_json = await self.decompression_manager.decompress(
                data, self.actual_data_type
            )
            self.current_image = await self.processor.run_async_process_valetudo_data(
                parsed_json
            )

    def get_map_image(self):
        """Get the current map image."""
        # If no image, return a gray image
        if not self.current_image:
            return Image.new("RGB",
                             (DEFAULT_IMAGE_SIZE.get("x"),
                              DEFAULT_IMAGE_SIZE.get("y")),
                             "gray")
        return self.current_image

    async def _handle_mqtt_camera_event(self) -> None:
        """Handle camera update signal from MQTT connector."""
        if self.is_rand256 and not self.shared.destinations:
            self.shared.destinations = await self.connector.get_destinations()
        LOGGER.debug("Received dispatcher signal for: %s", self.file_name)
        if await self.async_should_stream():
            await self.async_process_image()
            if self.current_image is not self._prev_image:
                self._prev_image = self.current_image.copy()
                self._prev_data_type = self.actual_data_type
                data = CameraImageData(
                    is_rand=self.is_rand256,
                    data_type=self.actual_data_type,
                    image_width=self.current_image.width,
                    image_height=self.current_image.height,
                    success=True,
                )
                LOGGER.debug("Camera update pushed: %s", self.file_name)
                return self.async_set_updated_data(VacuumData(camera=data))

        # No new data or failed update → update with last or minimal
        if self._prev_image:
            self.current_image = self._prev_image.copy()
        return None

    async def async_should_stream(self):
        """Determine if camera should stream based on vacuum state and new data."""
        new_data = await self.connector.is_data_available()
        should_stream = await self.state_manager.update_vacuum_state()
        return (should_stream and new_data) or not self._prev_image

    async def async_subscribe_mqtt(self) -> None:
        """Subscribe to MQTT topics."""
        if self._mqtt_subscribed:
            return

        try:
            LOGGER.debug("Subscribing to MQTT topics for: %s", self.file_name)
            await self.connector.async_subscribe_to_topics()
            self._mqtt_subscribed = True
            LOGGER.debug("MQTT subscription complete for: %s", self.file_name)
        except RuntimeError as err:
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
        except RuntimeError as err:
            LOGGER.error(
                "Failed to unsubscribe from MQTT for %s: %s", self.file_name, err
            )

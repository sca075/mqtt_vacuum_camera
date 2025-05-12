"""
MQTT Vacuum Camera Coordinator.
Version: 2025.3.0b0
"""

import asyncio
from datetime import timedelta
from typing import Optional

import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from valetudo_map_parser.config.shared import CameraShared, CameraSharedManager

from .common import get_camera_device_info
from .const import DEFAULT_NAME, LOGGER, SENSOR_NO_DATA
from .utils.connection.connector import ValetudoConnector


class MQTTVacuumCoordinator(DataUpdateCoordinator):
    """Coordinator for MQTT Vacuum Camera."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        vacuum_topic: str,
        rand256_vacuum: bool = False,
        polling_interval: timedelta = timedelta(seconds=3),
    ):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DEFAULT_NAME,
            update_interval=polling_interval,
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
        self.shared, self.file_name = self._init_shared_data(self.vacuum_topic)
        self.start_up_mqtt()
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
        self.in_sync_with_camera = True
        return self.shared, self.file_name

    async def async_update_camera_data(self, process: bool = True):
        """
        Fetch data from the MQTT topics.
        """
        try:
            async with async_timeout.timeout(10):
                # Fetch and process maps data from the MQTT connector
                return await self.connector.update_data(process)
        except Exception as err:
            LOGGER.error(
                "Error communicating with MQTT or processing data: %s",
                err,
                exc_info=True,
            )
            raise UpdateFailed(f"Error communicating with MQTT: {err}") from err

    async def async_update_sensor_data(self, sensor_data):
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

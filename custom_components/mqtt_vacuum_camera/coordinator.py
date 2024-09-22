"""MQTT Vacuum Camera Coordinator."""

from datetime import timedelta
import logging
from typing import Optional

import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .camera_shared import CameraShared, CameraSharedManager
from .common import get_camera_device_info
from .const import DEFAULT_NAME, SENSOR_NO_DATA
from .valetudo.MQTT.connector import ValetudoConnector

_LOGGER = logging.getLogger(__name__)


class MQTTVacuumCoordinator(DataUpdateCoordinator):
    """Coordinator for MQTT Vacuum Camera."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        vacuum_topic: str,
        polling_interval=timedelta(seconds=3),
    ):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DEFAULT_NAME,
            update_interval=polling_interval,
        )
        self.hass: HomeAssistant = hass
        self.vacuum_topic: str = vacuum_topic
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

    async def _async_update_data(self):
        """
        Fetch data from the MQTT topics for sensors.
        """
        if (self.sensor_data == SENSOR_NO_DATA) or (
            self.shared is not None and self.shared.vacuum_state != "docked"
        ):
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
                _LOGGER.error(f"Error fetching sensor data: {err}")
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
            _LOGGER.debug(f"Camera {file_name} Starting up..")

        return shared, file_name

    def start_up_mqtt(self) -> ValetudoConnector:
        """
        Initialize the MQTT Connector.
        """
        self.connector = ValetudoConnector(self.vacuum_topic, self.hass, self.shared)
        return self.connector

    def update_shared_data(self, dev_info: DeviceInfo) -> tuple[CameraShared, str]:
        """
        Create or update the instance of the shared data.
        """
        self.shared_manager.update_shared_data(dev_info)
        self.shared = self.shared_manager.get_instance()
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
        except ConfigEntryAuthFailed as err:
            raise ConfigEntryAuthFailed from err
        except Exception as err:
            _LOGGER.error(f"Error communicating with MQTT or processing data: {err}")
            raise UpdateFailed(f"Error communicating with MQTT: {err}") from err

    async def async_update_sensor_data(self, sensor_data):
        """
        Update the sensor data format before sending to the sensors.
        """
        if sensor_data:
            # Assume sensor_data is a dictionary or transform it into the expected format
            battery_level = await self.connector.get_battery_level()
            vacuum_state = await self.connector.get_vacuum_status()
            last_run_stats = sensor_data.get("last_run_stats", {})
            formatted_data = {
                "mainBrush": sensor_data.get("mainBrush", 0),
                "sideBrush": sensor_data.get("sideBrush", 0),
                "filter": sensor_data.get("filter", 0),
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
                "last_loaded_map": sensor_data.get("last_loaded_map", "None"),
            }
            return formatted_data
        return SENSOR_NO_DATA
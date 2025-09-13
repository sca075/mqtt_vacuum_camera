"""
MQTT Vacuum Camera Coordinator.
Version: 2025.8.0
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
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
        device_entity: ConfigEntry,
        vacuum_topic: str,
        rand256_vacuum: bool = False,
        connector: Optional[ValetudoConnector] = None,
        shared: Optional[CameraShared] = None,
        polling_interval: timedelta = timedelta(seconds=10),
    ):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DEFAULT_NAME,
            config_entry=device_entity,
            update_interval=polling_interval,
            update_method=self._async_update_data,
        )
        self.hass: HomeAssistant = hass
        self.vacuum_topic: str = vacuum_topic
        self.is_rand256: bool = rand256_vacuum
        self.device_entity: ConfigEntry = device_entity
        self.device_info: DeviceInfo = get_camera_device_info(hass, self.device_entity)
        self.shared_manager: Optional[CameraSharedManager] = None
        if shared:
            self.shared = shared
            self.shared.is_rand = self.is_rand256
            self.file_name = shared.file_name
        self.connector = connector
        self.in_sync_with_camera: bool = False
        self.sensor_data = SENSOR_NO_DATA

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

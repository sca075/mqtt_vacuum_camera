"""
MQTT Vacuum Camera Coordinator.
Version: 2025.10.0
"""

from __future__ import annotations

from typing import Optional

import async_timeout
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from valetudo_map_parser.config.shared import CameraSharedManager

from .common import get_camera_device_info
from .const import DEFAULT_NAME, LOGGER, SENSOR_NO_DATA
from .types import CoordinatorConfig, CoordinatorContext


class MQTTVacuumCoordinator(DataUpdateCoordinator):
    """Coordinator for MQTT Vacuum Camera."""

    def __init__(self, config: CoordinatorConfig):
        """Initialize the coordinator."""
        super().__init__(
            config.hass,
            LOGGER,
            name=DEFAULT_NAME,
            config_entry=config.device_entity,
            update_interval=config.polling_interval,
            update_method=self._async_update_data,
        )
        self.hass = config.hass
        self.vacuum_topic = config.vacuum_topic
        self.is_rand256 = config.is_rand256
        self.device_entity = config.device_entity

        # Initialize context with grouped attributes
        device_info = get_camera_device_info(config.hass, config.device_entity)
        shared = None
        file_name = None
        if config.shared:
            shared = config.shared
            shared.is_rand = self.is_rand256
            file_name = config.shared.file_name

        self.context = CoordinatorContext(
            shared=shared,
            file_name=file_name,
            connector=config.connector,
            device_info=device_info,
        )

        self.shared_manager: Optional[CameraSharedManager] = None
        self.in_sync_with_camera: bool = False
        self.sensor_data = SENSOR_NO_DATA

    async def _async_update_data(self):
        """
        Fetch data from the MQTT topics for sensors.
        """
        if self.context.shared is not None and self.context.connector:
            try:
                async with async_timeout.timeout(10):
                    # Fetch and process sensor data from the MQTT connector
                    sensor_data = await self.context.connector.get_rand256_attributes()
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
                battery_level = await self.context.connector.get_battery_level()
                vacuum_state = await self.context.connector.get_vacuum_status()
            except (AttributeError, ConnectionError) as err:
                LOGGER.warning("Failed to get vacuum status: %s", err, exc_info=True)
                return SENSOR_NO_DATA

            vacuum_room = self.context.shared.current_room or {"in_room": "Unsupported"}
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

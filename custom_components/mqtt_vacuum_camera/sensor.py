"""Sensors for Rand256."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import AREA_SQUARE_METERS, PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MQTTVacuumCoordinator
SCAN_INTERVAL = timedelta(seconds=3)
SENSOR_NO_DATA = {
    "mainBrush": 0,
    "sideBrush": 0,
    "filter": 0,
    "sensor": 0,
    "currentCleanTime": 0,
    "currentCleanArea": 0,
    "cleanTime": 0,
    "cleanArea": 0,
    "cleanCount": 0,
}
_LOGGER = logging.getLogger(__name__)

@dataclass
class VacuumSensorDescription(SensorEntityDescription):
    """A class that describes vacuum sensor entities."""
    attributes: tuple = ()
    parent_key: str = None
    keys: list[str] = None
    value: Callable = None

SENSOR_TYPES = {
    "consumable_main_brush": VacuumSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="mainBrush",
        icon="mdi:brush",
        device_class=SensorDeviceClass.DURATION,
        name="Main brush",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "consumable_side_brush": VacuumSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="sideBrush",
        icon="mdi:brush",
        device_class=SensorDeviceClass.DURATION,
        name="Side brush",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "consumable_filter": VacuumSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="filter",
        icon="mdi:air-filter",
        device_class=SensorDeviceClass.DURATION,
        name="Filter",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "battery": VacuumSensorDescription(
        native_unit_of_measurement=PERCENTAGE,
        key="battery",
        icon="mdi:battery",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "current_clean_time": VacuumSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="currentCleanTime",
        icon="mdi:timer-sand",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DURATION,
        name="Current clean time",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "current_clean_area": VacuumSensorDescription(
        native_unit_of_measurement=AREA_SQUARE_METERS,
        key="currentCleanArea",
        icon="mdi:texture-box",
        name="Current clean area",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "clean_count": VacuumSensorDescription(
        native_unit_of_measurement="",
        key="cleanCount",
        icon="mdi:counter",
        name="Total clean count",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "clean_time": VacuumSensorDescription(
        native_unit_of_measurement=UnitOfTime.MINUTES.SECONDS,
        key="cleanTime",
        icon="mdi:timer-sand",
        state_class=SensorStateClass.TOTAL_INCREASING,
        name="Total clean time",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "state": VacuumSensorDescription(
        key="state",
        icon="mdi:robot-vacuum",
        name="Vacuum state",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "last_run_start": VacuumSensorDescription(
        native_unit_of_measurement=UnitOfTime.HOURS.MINUTES.SECONDS,
        key="last_run_stats.startTime",
        icon="mdi:clock-start",
        name="Last run start time",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "last_run_end": VacuumSensorDescription(
        native_unit_of_measurement=UnitOfTime.HOURS,
        key="last_run_stats.endTime",
        icon="mdi:clock-end",
        name="Last run end time",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "last_run_duration": VacuumSensorDescription(
        native_unit_of_measurement=UnitOfTime.MINUTES,
        key="last_run_stats.duration",
        icon="mdi:timer",
        name="Last run duration",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "last_run_area": VacuumSensorDescription(
        native_unit_of_measurement=AREA_SQUARE_METERS,
        key="last_run_stats.area",
        icon="mdi:texture-box",
        name="Last run area",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Sensors for bin and map-related data
    "last_bin_out": VacuumSensorDescription(
        native_unit_of_measurement=UnitOfTime.DAYS,
        key="last_bin_out",
        icon="mdi:delete",
        name="Last bin out time",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "last_bin_full": VacuumSensorDescription(
        native_unit_of_measurement=UnitOfTime.DAYS,
        key="last_bin_full",
        icon="mdi:delete-alert",
        name="Last bin full time",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "last_loaded_map": VacuumSensorDescription(
        native_unit_of_measurement="",
        key="last_loaded_map",
        icon="mdi:map",
        name="Last loaded map",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


class VacuumSensor(CoordinatorEntity, SensorEntity):
    """Representation of a vacuum sensor."""

    entity_description: VacuumSensorDescription

    def __init__(self, coordinator: MQTTVacuumCoordinator, description: VacuumSensorDescription, sensor_type: str):
        """Initialize the vacuum sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.coordinator = coordinator
        self._attr_native_value = None
        self._attr_unique_id = f"{coordinator.file_name}_{sensor_type}"
        self.entity_id = f"sensor.{coordinator.file_name}_{sensor_type}"

    @callback
    async def async_update(self):
        """Update the sensor's state."""
        if self.coordinator.last_update_success:
            await self._handle_coordinator_update()

    @property
    def should_poll(self) -> bool:
        """Indicate if the sensor should poll for updates."""
        return True  # This will tell Home Assistant to poll for data

    @callback
    async def _extract_attributes(self):
        """Return state attributes with valid values."""
        data = self.coordinator.sensor_data
        if self.entity_description.parent_key:
            data = getattr(data, self.entity_description.key)
            if data is None:
                return
        return {
            attr: getattr(data, attr)
            for attr in self.entity_description.attributes
            if hasattr(data, attr)
        }

    @callback
    async def _handle_coordinator_update(self):
        """Fetch the latest state from the coordinator and update the sensor."""
        data = self.coordinator.sensor_data
        _LOGGER.debug(f"{self.coordinator.file_name} getting sensors update: {data}")
        if data is None:
            data = SENSOR_NO_DATA

        # Fetch the value based on the key in the description
        native_value = data.get(self.entity_description.key, 0)
        _LOGGER.debug(f"{self.entity_description.key}, return {native_value}")

        if native_value is not None:
            self._attr_native_value = native_value
        else:
            self._attr_native_value = 0  # Set to None if the value is missing or invalid

        self.async_write_ha_state()


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up vacuum sensors based on a config entry."""
    coordinator = hass.data["mqtt_vacuum_camera"][config_entry.entry_id]["coordinator"]

    # Create and add sensor entities
    sensors = []
    for sensor_type, description in SENSOR_TYPES.items():
        sensors.append(VacuumSensor(coordinator, description, sensor_type))

    async_add_entities(sensors, update_before_add=False)

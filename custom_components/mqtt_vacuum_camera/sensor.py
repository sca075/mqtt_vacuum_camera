"""Sensors for Rand256.
Version 2024.12.0
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfArea, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_VACUUM_IDENTIFIERS, DOMAIN, SENSOR_NO_DATA
from .coordinator import MQTTVacuumCoordinator

SCAN_INTERVAL = timedelta(seconds=3)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
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
        name="Main brush",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "consumable_side_brush": VacuumSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="sideBrush",
        icon="mdi:brush",
        name="Side brush",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "consumable_filter": VacuumSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="filter",
        icon="mdi:air-filter",
        name="Filter",
        state_class=SensorStateClass.MEASUREMENT,
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
        name="Current clean time",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "current_clean_area": VacuumSensorDescription(
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        key="currentCleanArea",
        icon="mdi:texture-box",
        name="Current clean area",
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "clean_count": VacuumSensorDescription(
        key="cleanCount",
        icon="mdi:counter",
        name="Total clean count",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "clean_time": VacuumSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="cleanTime",
        icon="mdi:timer-sand",
        name="Total clean time",
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "state": VacuumSensorDescription(
        key="state",
        icon="mdi:robot-vacuum",
        name="Vacuum state",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "last_run_start": VacuumSensorDescription(
        key="last_run_start",
        icon="mdi:clock-start",
        name="Last run start time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "last_run_end": VacuumSensorDescription(
        key="last_run_end",
        icon="mdi:clock-end",
        name="Last run end time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "last_run_duration": VacuumSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="last_run_duration",
        icon="mdi:timer",
        name="Last run duration",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "last_run_area": VacuumSensorDescription(
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        key="last_run_area",
        icon="mdi:texture-box",
        name="Last run area",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "last_bin_out": VacuumSensorDescription(
        key="last_bin_out",
        icon="mdi:delete",
        name="Last bin out time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "last_bin_full": VacuumSensorDescription(
        key="last_bin_full",
        icon="mdi:delete-alert",
        name="Last bin full time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "last_loaded_map": VacuumSensorDescription(
        key="last_loaded_map",
        icon="mdi:map",
        name="Last loaded map",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda v, _: v if isinstance(v, str) else "Unknown",
    ),
    "robot_in_room": VacuumSensorDescription(
        key="robot_in_room",
        icon="mdi:location-enter",
        name="Current Room",
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda v, _: v if isinstance(v, str) else "Unsupported",
    ),
}


class VacuumSensor(CoordinatorEntity, SensorEntity):
    """Representation of a vacuum sensor."""

    entity_description: VacuumSensorDescription

    def __init__(
        self,
        coordinator: MQTTVacuumCoordinator,
        description: VacuumSensorDescription,
        sensor_type: str,
        vacuum_identifier,
    ):
        """Initialize the vacuum sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.coordinator = coordinator
        self._attr_native_value = None
        self._attr_unique_id = f"{coordinator.file_name}_{sensor_type}"
        self.entity_id = f"sensor.{coordinator.file_name}_{sensor_type}"
        self._identifiers = vacuum_identifier

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal from Home Assistant."""
        await super().async_will_remove_from_hass()

    @callback
    async def async_update(self):
        """Update the sensor's state."""
        if self.coordinator.last_update_success:
            await self.async_handle_coordinator_update()

    @property
    def should_poll(self) -> bool:
        """Indicate if the sensor should poll for updates."""
        return True

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
    async def async_handle_coordinator_update(self):
        """Fetch the latest state from the coordinator and update the sensor."""
        data = self.coordinator.sensor_data
        if data is None:
            data = SENSOR_NO_DATA

        # Fetch the value based on the key in the description
        native_value = data.get(self.entity_description.key, 0)
        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            # Convert the Unix timestamp to datetime
            try:
                native_value = process_timestamp(native_value)
            except (ValueError, TypeError):
                native_value = None
        elif self.entity_description.device_class == SensorDeviceClass.DURATION:
            # Convert the Unix timestamp to datetime
            try:
                native_value = convert_duration(native_value)
            except (ValueError, TypeError):
                native_value = None

        if native_value is not None:
            self._attr_native_value = native_value
        else:
            self._attr_native_value = (
                0  # Set to None if the value is missing or invalid
            )

        self.async_write_ha_state()


def convert_duration(seconds):
    """Convert seconds in days"""
    # Create a timedelta object from seconds
    time_delta = timedelta(seconds=float(seconds))
    if not time_delta:
        return seconds
    return time_delta.total_seconds()


def process_timestamp(native_value):
    """Convert vacuum times in local time"""
    if native_value is None or native_value <= 0:
        return datetime.fromtimestamp(0, timezone.utc)
    try:
        # Convert milliseconds to seconds
        utc_time = datetime.fromisoformat(
            datetime.fromtimestamp(float(native_value) / 1000, timezone.utc)
            .astimezone()
            .isoformat()
        )

        return utc_time
    except ValueError:
        _LOGGER.debug(f"Invalid timestamp: {native_value}")
        return None


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up vacuum sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    vacuum_identifier = hass.data[DOMAIN][config_entry.entry_id][
        CONF_VACUUM_IDENTIFIERS
    ]
    # Create and add sensor entities
    sensors = []
    for sensor_type, description in SENSOR_TYPES.items():
        sensors.append(
            VacuumSensor(coordinator, description, sensor_type, vacuum_identifier)
        )
    async_add_entities(sensors, update_before_add=False)

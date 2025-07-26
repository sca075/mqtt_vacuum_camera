"""
MQTT Vacuum Camera Entity
Camera just handles PIL to bytes conversion, coordinator does all processing.
Version: 2025.7.1
"""

from __future__ import annotations


from typing import Any, Self

from homeassistant import config_entries, core
from homeassistant.components.camera import Camera
from homeassistant.helpers import config_validation as cv

from .coordinator import CameraCoordinator
from .entity import MQTTVacuumCoordinatorEntity
from .const import (
    DOMAIN,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
) -> None:
    """Setup camera from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    coordinators = hass.data[DOMAIN][config_entry.entry_id]["coordinators"]
    camera_coordinator = coordinators["camera"]
    # Update our config to and eventually add or remove option.
    if config_entry.options:
        config.update(config_entry.options)

    # Create camera entity
    camera = [MQTTVacuumCamera(camera_coordinator, config)]

    # Add entities
    async_add_entities(camera, update_before_add=False)


class MQTTVacuumCamera(MQTTVacuumCoordinatorEntity, Camera):
    _attr_has_entity_name = True

    def __init__(
        self: Self, coordinator: CameraCoordinator, device_info: dict[str, Any]
    ) -> None:
        MQTTVacuumCoordinatorEntity.__init__(self, coordinator, device_info)
        Camera.__init__(self)
        
        self.content_type = "image/png"

    @property
    def frame_interval(self) -> float:
        """Camera Frame Interval"""
        return self._attr_frame_interval

    @property
    def name(self) -> str:
        """Camera Entity Name"""
        return self._attr_name

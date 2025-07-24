"""
MQTT Vacuum Camera Entity
Camera just handles PIL to bytes conversion, coordinator does all processing.
Version: 2025.7.1
"""

from __future__ import annotations


from typing import Any, Self

from homeassistant import config_entries, core
from homeassistant.components.image import ImageEntity
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
    image = [MQTTVacuumImage(camera_coordinator, config)]

    # Add entities
    async_add_entities(image, update_before_add=False)


class MQTTVacuumImage(MQTTVacuumCoordinatorEntity, ImageEntity):
    _attr_has_entity_name = True

    def __init__(
        self: Self, coordinator: CameraCoordinator, device_info: dict[str, Any]
    ) -> None:
        MQTTVacuumCoordinatorEntity.__init__(self, coordinator, device_info)
        ImageEntity.__init__(self, coordinator.hass)
        self.content_type = "image/png"
        # coordinator.image_entity = self

    @property
    def name(self) -> str:
        """Camera Entity Name"""
        return f"Image {self._attr_name}"

    def image(self: Self) -> bytes | None:
        """Return bytes of image"""
        return self.Image

    @property
    def image_last_updated(self: Self):
        return self._last_image_time

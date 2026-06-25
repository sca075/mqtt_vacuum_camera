"""
Camera
Last Updated on version: 2026.3.1
"""

from __future__ import annotations

from datetime import timedelta

from homeassistant import config_entries, core
from homeassistant.helpers import config_validation as cv

from .const import CAMERA_SCAN_INTERVAL_S, DOMAIN
from .entity import MQTTCamera, MQTTCameraMPEG

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)  # pylint: disable=invalid-name

SCAN_INTERVAL = timedelta(seconds=CAMERA_SCAN_INTERVAL_S)  # pylint: disable=invalid-name


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
) -> None:
    """Setup camera from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    # Update our config to and eventually add or remove option.
    if config_entry.options:
        config.update(config_entry.options)
    if coordinator.context.shared.get_content_type == "image/jpeg":
        camera = [MQTTCameraMPEG(coordinator, config)]
    else:
        camera = [MQTTCamera(coordinator, config)]
    async_add_entities(camera, update_before_add=True)

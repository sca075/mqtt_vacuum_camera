"""Camera-related services for the MQTT Vacuum Camera integration."""

import logging


from homeassistant.core import ServiceCall, HomeAssistant
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import SERVICE_RELOAD

from ...utils.files_operations import async_clean_up_all_auto_crop_files

_LOGGER = logging.getLogger(__name__)

async def reset_trims(hass: HomeAssistant, call: ServiceCall, domain: str) -> None:
    """Action Reset Map Trims."""
    _LOGGER.debug(f"Resetting trims for {domain}")
    await async_clean_up_all_auto_crop_files(hass)
    await hass.services.async_call(domain, SERVICE_RELOAD)
    hass.bus.async_fire(f"event_{domain}_reset_trims", context=call.context)


async def reload_config(hass: HomeAssistant, domain: str) -> None:
    """Reload the camera platform for all entities in the integration."""
    _LOGGER.debug(f"Reloading the config entry for all {domain} entities")
    camera_entries = hass.config_entries.async_entries(domain)

    for camera_entry in camera_entries:
        if camera_entry.state == ConfigEntryState.LOADED:
            _LOGGER.debug(f"Unloading entry: {camera_entry.entry_id}")
            await hass.config_entries.async_unload(camera_entry.entry_id)

            _LOGGER.debug(f"Reloading entry: {camera_entry.entry_id}")
            await hass.config_entries.async_setup(camera_entry.entry_id)
        else:
            _LOGGER.debug(
                f"Skipping entry {camera_entry.entry_id} as it is NOT_LOADED"
            )

    hass.bus.async_fire(f"event_{domain}_reloaded")

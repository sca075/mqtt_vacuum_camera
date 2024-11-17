"""Camera-related services for the MQTT Vacuum Camera integration."""

import asyncio
import async_timeout
import logging


from homeassistant.core import ServiceCall, HomeAssistant
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import SERVICE_RELOAD

from ...utils.files_operations import async_clean_up_all_auto_crop_files

_LOGGER = logging.getLogger(__name__)

async def reset_trims(hass: HomeAssistant, call: ServiceCall, domain: str) -> None:
    """Action Reset Map Trims."""
    _LOGGER.debug(f"Resetting trims for {domain}")
    try:
        await async_clean_up_all_auto_crop_files(hass)
        await hass.services.async_call(domain, SERVICE_RELOAD)
        hass.bus.async_fire(f"event_{domain}_reset_trims", context=call.context)
    except Exception as err:
        _LOGGER.error(f"Error resetting trims: {err}")


async def reload_config(hass: HomeAssistant, domain: str) -> None:
    """Reload the camera platform for all entities in the integration."""
    _LOGGER.debug(f"Reloading the config entry for all {domain} entities")
    camera_entries = hass.config_entries.async_entries(domain)
    total_entries = len(camera_entries)
    processed = 0

    for camera_entry in camera_entries:
        processed += 1
        _LOGGER.info(f"Processing entry {processed}/{total_entries}")
        if camera_entry.state == ConfigEntryState.LOADED:
            _LOGGER.debug(f"Unloading entry: {camera_entry.entry_id}")
            try:
                async with async_timeout.timeout(30):
                    await hass.config_entries.async_unload(camera_entry.entry_id)

                _LOGGER.debug(f"Reloading entry: {camera_entry.entry_id}")
                await hass.config_entries.async_setup(camera_entry.entry_id)
            except asyncio.TimeoutError:
                _LOGGER.error(f"Timeout while processing entry {camera_entry.entry_id}")
                continue
            except Exception as err:
                _LOGGER.error(f"Error processing entry {camera_entry.entry_id}: {err}")
                continue
        else:
            _LOGGER.debug(
                f"Skipping entry {camera_entry.entry_id} as it is NOT_LOADED"
            )

    hass.bus.async_fire(f"event_{domain}_reloaded", {
        "processed": processed,
        "total": total_entries
    })

"""Camera-related services for the MQTT Vacuum Camera integration."""

import logging
import asyncio
import async_timeout

from homeassistant.core import ServiceCall, HomeAssistant
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import SERVICE_RELOAD

from ...utils.files_operations import async_clean_up_all_auto_crop_files
from ...const import  DOMAIN

_LOGGER = logging.getLogger(__name__)

async def reset_trims( call: ServiceCall, hass: HomeAssistant) -> None:
    """Action Reset Map Trims."""
    _LOGGER.debug(f"Resetting trims for {DOMAIN}")
    try:
        await async_clean_up_all_auto_crop_files(hass)
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD)
        hass.bus.async_fire(f"event_{DOMAIN}_reset_trims", context=call.context)
    except Exception as err:
        _LOGGER.error(f"Error resetting trims: {err}")


async def reload_camera_config(call: ServiceCall, hass: HomeAssistant) -> None:
    """Reload the camera platform for all entities in the integration."""

    _LOGGER.debug(f"Reloading the config entry for all {DOMAIN} entities")
    camera_entries = hass.config_entries.async_entries(DOMAIN)
    total_entries = len(camera_entries)
    processed = 0

    for camera_entry in camera_entries:
        processed += 1
        _LOGGER.info(f"Processing entry {processed}/{total_entries}")
        if camera_entry.state == ConfigEntryState.LOADED:
            try:
                with async_timeout.timeout(10):
                    _LOGGER.debug(f"Reloading entry: {camera_entry.entry_id}")
                    hass.config_entries.async_schedule_reload(camera_entry.entry_id)
            except asyncio.TimeoutError:
                _LOGGER.error(f"Timeout processing entry {camera_entry.entry_id}")
            except Exception as err:
                _LOGGER.error(f"Error processing entry {camera_entry.entry_id}: {err}")
                continue
        else:
            _LOGGER.debug(
                f"Skipping entry {camera_entry.entry_id} as it is NOT_LOADED"
            )

    hass.bus.async_fire(f"event_{DOMAIN}_reloaded",
                        event_data= {
                            "processed": processed,
                            "total": total_entries,
                        },
                        context=call.context)

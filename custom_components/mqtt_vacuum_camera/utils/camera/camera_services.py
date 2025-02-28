"""Camera-related services for the MQTT Vacuum Camera integration."""

import asyncio

import async_timeout
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall

from ...common import get_entity_id
from ...const import DOMAIN, LOGGER
from ...utils.files_operations import async_clean_up_all_auto_crop_files


async def reset_trims(call: ServiceCall, hass: HomeAssistant) -> None:
    """Action Reset Map Trims."""
    LOGGER.debug("Resetting trims for %s", DOMAIN)
    try:
        await async_clean_up_all_auto_crop_files(hass)
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD)
        hass.bus.async_fire(f"event_{DOMAIN}_reset_trims", context=call.context)
    except ValueError as err:
        LOGGER.error("Error resetting trims: %s", err, exc_info=True)


async def reload_camera_config(call: ServiceCall, hass: HomeAssistant) -> None:
    """Reload the camera platform for all entities in the integration."""

    LOGGER.debug("Reloading the config entry for all %s entities", DOMAIN)
    camera_entries = hass.config_entries.async_entries(DOMAIN)
    total_entries = len(camera_entries)
    processed = 0

    for camera_entry in camera_entries:
        processed += 1
        LOGGER.info("Processing entry %r / %r", processed, total_entries)
        if camera_entry.state == ConfigEntryState.LOADED:
            try:
                with async_timeout.timeout(10):
                    LOGGER.debug("Reloading entry: %s", camera_entry.entry_id)
                    hass.config_entries.async_schedule_reload(camera_entry.entry_id)
            except asyncio.TimeoutError:
                LOGGER.error(
                    "Timeout processing entry %s", camera_entry.entry_id, exc_info=True
                )
            except ValueError as err:
                LOGGER.error(
                    "Error processing entry %s: %s", camera_entry.entry_id, err
                )
                continue
        else:
            LOGGER.debug("Skipping entry %s as it is NOT_LOADED", camera_entry.entry_id)

    hass.bus.async_fire(
        f"event_{DOMAIN}_reloaded",
        event_data={
            "processed": processed,
            "total": total_entries,
        },
        context=call.context,
    )


async def obstacle_view(call: ServiceCall, hass: HomeAssistant) -> None:
    """Action to download and show the obstacles in the maps."""
    coordinates_x = call.data.get("coordinates_x")
    coordinates_y = call.data.get("coordinates_y")

    # attempt to get the entity_id or device.
    entity_id = call.data.get("entity_id")
    device_id = call.data.get("device_id")
    # resolve the entity_id if not provided.
    camera_entity_id = get_entity_id(entity_id, device_id, hass, "camera")[0]

    LOGGER.debug("Obstacle view for %s", camera_entity_id)
    LOGGER.debug(
        "Firing event to search and view obstacle at coordinates %r, %r",
        coordinates_x,
        coordinates_y,
    )
    hass.bus.async_fire(
        event_type=f"{DOMAIN}_obstacle_coordinates",
        event_data={
            "entity_id": camera_entity_id,
            "coordinates": {"x": coordinates_x, "y": coordinates_y},
        },
        context=call.context,
    )

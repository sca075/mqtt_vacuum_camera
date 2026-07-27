"""Camera-related services for the MQTT Vacuum Camera integration."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from ...common import create_floor_data, get_entity_id
from ...const import CONF_CURRENT_FLOOR, CONF_FLOORS_DATA, DOMAIN, LOGGER


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
                LOGGER.debug("Reloading entry: %s", camera_entry.entry_id)
                hass.config_entries.async_schedule_reload(camera_entry.entry_id)
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


def _get_config_entry_from_camera(camera_entity_id: str, hass: HomeAssistant):
    """Return the ConfigEntry for a camera entity_id, or None if not found."""
    entity_reg = er.async_get(hass)
    entity_entry = entity_reg.async_get(camera_entity_id)
    if not entity_entry or not entity_entry.config_entry_id:
        LOGGER.warning(
            "Camera entity %s not found in entity registry", camera_entity_id
        )
        return None
    entry = hass.config_entries.async_get_entry(entity_entry.config_entry_id)
    if not entry:
        LOGGER.warning("Config entry not found for camera %s", camera_entity_id)
    return entry


def _resolve_camera_entity_id(call: ServiceCall, hass: HomeAssistant) -> str | None:
    """Resolve the first camera entity_id from a service call."""
    entity_id = call.data.get("entity_id")
    device_id = call.data.get("device_id")
    resolved = get_entity_id(entity_id, device_id, hass, "camera")
    if not resolved:
        LOGGER.warning("Could not resolve camera entity from service call")
        return None
    return resolved[0] if isinstance(resolved, list) else resolved


async def camera_select_floor(call: ServiceCall, hass: HomeAssistant) -> None:
    """Select the active floor for a camera entity."""
    floor_id = call.data.get("floor_id")
    if not floor_id:
        LOGGER.warning("camera_select_floor: floor_id is required")
        return

    camera_entity_id = _resolve_camera_entity_id(call, hass)
    if not camera_entity_id:
        return

    entry = _get_config_entry_from_camera(camera_entity_id, hass)
    if not entry:
        return

    floors_data = entry.options.get(CONF_FLOORS_DATA, {})
    if floors_data and floor_id not in floors_data:
        LOGGER.warning(
            "camera_select_floor: floor_id '%s' is not configured for %s",
            floor_id,
            camera_entity_id,
        )
        return

    updated_options = {**entry.options, CONF_CURRENT_FLOOR: floor_id}
    hass.config_entries.async_update_entry(entry, options=updated_options)
    hass.bus.async_fire(
        f"event_{DOMAIN}_floor_selected",
        {"entity_id": camera_entity_id, "floor_id": floor_id},
        context=call.context,
    )


async def camera_update_floor_data(call: ServiceCall, hass: HomeAssistant) -> None:
    """Save current auto-calculated trims into the active floor's FloorData."""
    camera_entity_id = _resolve_camera_entity_id(call, hass)
    if not camera_entity_id:
        return

    entry = _get_config_entry_from_camera(camera_entity_id, hass)
    if not entry:
        return

    hass_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator = hass_data.get("coordinator")
    if not coordinator:
        LOGGER.warning(
            "camera_update_floor_data: coordinator not available for %s",
            camera_entity_id,
        )
        return

    floor_id = call.data.get("floor_id") or entry.options.get(
        CONF_CURRENT_FLOOR, "floor_0"
    )
    floors_data = dict(entry.options.get(CONF_FLOORS_DATA, {}))
    floor_data_dict = floors_data.get(floor_id, {})

    trims_dict = coordinator.context.shared.trims.to_dict()
    updated_floor = create_floor_data(
        floor_name=floor_id,
        trim_up=trims_dict.get("trim_up", 0),
        trim_down=trims_dict.get("trim_down", 0),
        trim_left=trims_dict.get("trim_left", 0),
        trim_right=trims_dict.get("trim_right", 0),
        map_name=floor_data_dict.get("map_name", ""),
    )

    floors_data[floor_id] = updated_floor.to_dict()
    updated_options = {
        **entry.options,
        CONF_FLOORS_DATA: floors_data,
        "trims_data": updated_floor.trims.to_dict(),
    }
    hass.config_entries.async_update_entry(entry, options=updated_options)
    hass.bus.async_fire(
        f"event_{DOMAIN}_floor_data_updated",
        {"entity_id": camera_entity_id, "floor_id": floor_id},
        context=call.context,
    )

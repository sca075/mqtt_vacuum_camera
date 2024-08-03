"""MQTT Vacuum Camera.
Version: 2024.08.0"""


import glob
import logging
import os
import shutil

from homeassistant import config_entries, core
from homeassistant.components import mqtt
from homeassistant.const import (
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    SERVICE_RELOAD,
    Platform,
)
from homeassistant.core import ServiceCall, ServiceResponse
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.reload import async_register_admin_service
from homeassistant.helpers.storage import STORAGE_DIR

from .common import (
    get_device_info,
    get_entity_identifier_from_mqtt,
    get_vacuum_mqtt_topic,
    get_vacuum_unique_id_from_mqtt_topic,
    update_options,
)
from .const import (
    CAMERA_STORAGE,
    CONF_MQTT_HOST,
    CONF_MQTT_PASS,
    CONF_MQTT_USER,
    CONF_VACUUM_CONFIG_ENTRY_ID,
    CONF_VACUUM_CONNECTION_STRING,
    CONF_VACUUM_IDENTIFIERS,
    DOMAIN,
)
from .utils.files_operations import (
    async_get_translations_vacuum_id,
    async_rename_room_description,
    async_reset_map_trims,
)

PLATFORMS = [Platform.CAMERA]
_LOGGER = logging.getLogger(__name__)


async def options_update_listener(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""

    async def _reload_config(call: ServiceCall) -> None:
        """Reload the platforms."""
        await async_unload_entry(hass, entry)
        await async_setup_entry(hass, entry)
        hass.bus.async_fire(f"event_{DOMAIN}_reloaded", context=call.context)

    async def reset_trims(call: ServiceCall) -> ServiceResponse:
        """Search in the date range and return the matching items."""
        entity_ids = call.data.get("entity_id")
        _LOGGER.debug(f"Resetting trims for {entity_ids}")
        items = await async_reset_map_trims(hass, entity_ids)
        await hass.services.async_call(DOMAIN, "reload")
        return {"done": items}

    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(entry.data)

    vacuum_entity_id, vacuum_device = get_device_info(
        hass_data[CONF_VACUUM_CONFIG_ENTRY_ID], hass
    )

    if not vacuum_entity_id:
        raise ConfigEntryNotReady(
            "Unable to lookup vacuum's entity ID. Was it removed?"
        )

    mqtt_topic_vacuum = get_vacuum_mqtt_topic(vacuum_entity_id, hass)
    if not mqtt_topic_vacuum:
        raise ConfigEntryNotReady("MQTT was not ready yet, automatically retrying")

    hass_data.update(
        {
            CONF_VACUUM_CONNECTION_STRING: "/".join(mqtt_topic_vacuum.split("/")[:-1]),
            CONF_VACUUM_IDENTIFIERS: vacuum_device.identifiers,
            CONF_UNIQUE_ID: entry.unique_id,
        }
    )

    # Registers update listener to update config entry when options are updated.
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)
    # Store a reference to the unsubscribe function to clean up if an entry is unloaded.
    hass_data["unsub_options_update_listener"] = unsub_options_update_listener
    hass.data[DOMAIN][entry.entry_id] = hass_data

    # Register Services
    hass.services.async_register(DOMAIN, "reset_trims", reset_trims)
    if not hass.services.has_service(DOMAIN, SERVICE_RELOAD):
        async_register_admin_service(hass, DOMAIN, SERVICE_RELOAD, _reload_config)

    # Forward the setup to the camera platform.
    await hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, ["camera"])
    )
    return True


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Remove config entry from domain.
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        entry_data["unsub_options_update_listener"]()
        hass.services.async_remove(DOMAIN, "reset_trims")
        hass.services.async_remove(DOMAIN, SERVICE_RELOAD)

    return unload_ok


def find_vacuum_files(directory) -> list[str] or None:
    """Find all 'room_data*.json' files and extract vacuum names."""
    # Create the full path pattern for glob to match
    path_pattern = os.path.join(directory, "room_data*.json")
    # Find all files matching the pattern
    files = glob.glob(path_pattern)
    if not files:
        _LOGGER.debug(f"No room data files found in {directory}.")
        return None
    # Extract vacuum names from filenames
    vacuum_names = [
        os.path.splitext(os.path.basename(file))[0].split("room_data_")[1]
        for file in files
    ]
    return vacuum_names


# noinspection PyCallingNonCallable
async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    """Set up the Valetudo Camera Custom component from yaml configuration."""

    async def handle_homeassistant_stop(event):
        """Handle Home Assistant stop event."""
        _LOGGER.info("Home Assistant is stopping. Writing down the rooms data.")
        storage = hass.config.path(STORAGE_DIR, CAMERA_STORAGE)
        if not os.path.exists(storage):
            _LOGGER.debug(f"Storage path: {storage} do not exists. Aborting!")
            return False
        vacuum_entity_id = await async_get_translations_vacuum_id(storage)
        if not vacuum_entity_id:
            _LOGGER.debug("No vacuum room data found. Aborting!")
            return False
        _LOGGER.debug(f"Writing down the rooms data for {vacuum_entity_id}.")
        result = await async_rename_room_description(hass, vacuum_entity_id)
        await hass.async_block_till_done()
        return True

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_FINAL_WRITE, handle_homeassistant_stop
    )

    # Make sure MQTT integration is enabled and the client is available
    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration is not available")
        return False
    hass.data.setdefault(DOMAIN, {})
    return True


async def move_data_to_valetudo_camera(storage):
    """Move files from .storage folder to valetudo_camera folder."""
    if os.path.exists(storage):
        storage_folder = f"{storage}/{CAMERA_STORAGE}"
        _LOGGER.debug(f"Creating the {storage_folder} path.")
        try:
            os.mkdir(storage_folder)
        except FileExistsError:
            _LOGGER.debug(f"Path {storage_folder} already exist.")
        # Move files matching the patterns to the valetudo_camera folder
        else:
            file_patterns = ["*.zip", "*.png", "*.log", "*.raw"]
            for pattern in file_patterns:
                files_to_move = glob.glob(os.path.join(storage_folder, pattern))
                for file_path in files_to_move:
                    file_name = os.path.basename(file_path)
                    destination_path = os.path.join(storage_folder, file_name)
                    if os.path.exists(file_path):
                        shutil.move(file_path, destination_path)
                        _LOGGER.debug(f"Moved {file_name} to valetudo_camera folder.")
                    else:
                        _LOGGER.debug(f"File {file_name} not found in .storage folder.")
    else:
        _LOGGER.warning(f"{storage} do not exists.")

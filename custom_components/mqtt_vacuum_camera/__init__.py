"""MQTT Vacuum Camera.
Version: 2024.08.1"""

import logging
import os

from homeassistant import config_entries, core
from homeassistant.components import mqtt
from homeassistant.const import (
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    SERVICE_RELOAD,
    Platform,
)
from homeassistant.core import ServiceCall
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
    async_clean_up_all_auto_crop_files,
    async_get_translations_vacuum_id,
    async_rename_room_description,
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
        """Reload the camera platform for all entities in the integration."""
        _LOGGER.debug("Reloading the config entry for all camera entities")

        # Retrieve all config entries associated with the DOMAIN
        camera_entries = hass.config_entries.async_entries(DOMAIN)

        # Iterate over each config entry
        for camera_entry in camera_entries:
            _LOGGER.debug(f"Unloading entry: {camera_entry.entry_id}")
            await async_unload_entry(hass, camera_entry)

            _LOGGER.debug(f"Reloading entry: {camera_entry.entry_id}")
            await async_setup_entry(hass, camera_entry)

        # Optionally, trigger other reinitialization steps if needed
        hass.bus.async_fire(f"event_{DOMAIN}_reloaded", context=call.context)

    async def reset_trims(call: ServiceCall) -> None:
        """Action Reset Map Trims."""
        _LOGGER.debug(f"Resetting trims for {DOMAIN}")
        await async_clean_up_all_auto_crop_files(hass)
        await hass.services.async_call(DOMAIN, "reload")
        hass.bus.async_fire(f"event_{DOMAIN}_reset_trims", context=call.context)

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
    _LOGGER.debug(f"unloading {entry.entry_id}")
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Remove config entry from domain.
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        entry_data["unsub_options_update_listener"]()
        # Remove services
        hass.services.async_remove(DOMAIN, "reset_trims")
        hass.services.async_remove(DOMAIN, SERVICE_RELOAD)

    return unload_ok


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

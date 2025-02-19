"""MQTT Vacuum Camera.
Version: 2025.2.2"""

from functools import partial
import logging
import os

from homeassistant import config_entries, core
from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    SERVICE_RELOAD,
    Platform,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.reload import async_register_admin_service
from homeassistant.helpers.storage import STORAGE_DIR

from .common import get_vacuum_device_info, get_vacuum_mqtt_topic, update_options
from .const import (
    CAMERA_STORAGE,
    CONF_VACUUM_CONFIG_ENTRY_ID,
    CONF_VACUUM_CONNECTION_STRING,
    CONF_VACUUM_IDENTIFIERS,
    DOMAIN,
)
from .coordinator import MQTTVacuumCoordinator
from .utils.camera.camera_services import (
    obstacle_view,
    reload_camera_config,
    reset_trims,
)
from .utils.files_operations import (
    async_get_translations_vacuum_id,
    async_rename_room_description,
)
from .utils.vacuum.mqtt_vacuum_services import (
    async_register_vacuums_services,
    async_remove_vacuums_services,
    is_rand256_vacuum,
)

PLATFORMS = [Platform.CAMERA, Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def options_update_listener(hass: core.HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_setup_entry(hass: core.HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""

    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(entry.data)

    vacuum_entity_id, vacuum_device = get_vacuum_device_info(
        hass_data[CONF_VACUUM_CONFIG_ENTRY_ID], hass
    )

    if not vacuum_entity_id:
        raise ConfigEntryNotReady(
            "Unable to lookup vacuum's entity ID. Was it removed?"
        )

    mqtt_topic_vacuum = get_vacuum_mqtt_topic(vacuum_entity_id, hass)
    if not mqtt_topic_vacuum:
        raise ConfigEntryNotReady("MQTT was not ready yet, automatically retrying")

    is_rand256 = is_rand256_vacuum(vacuum_device)

    data_coordinator = MQTTVacuumCoordinator(hass, entry, mqtt_topic_vacuum, is_rand256)

    hass_data.update(
        {
            CONF_VACUUM_CONNECTION_STRING: mqtt_topic_vacuum,
            CONF_VACUUM_IDENTIFIERS: vacuum_device.identifiers,
            CONF_UNIQUE_ID: entry.unique_id,
            "coordinator": data_coordinator,
            "is_rand256": is_rand256,
        }
    )
    # Register Services
    if not hass.services.has_service(DOMAIN, SERVICE_RELOAD):
        async_register_admin_service(
            hass, DOMAIN, SERVICE_RELOAD, partial(reload_camera_config, hass=hass)
        )
        hass.services.async_register(
            DOMAIN, "reset_trims", partial(reset_trims, hass=hass)
        )
        hass.services.async_register(
            DOMAIN, "obstacle_view", partial(obstacle_view, hass=hass)
        )
        await async_register_vacuums_services(hass, data_coordinator)
    # Registers update listener to update config entry when options are updated.
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)
    # Store a reference to the unsubscribe function to clean up if an entry is unloaded.
    hass_data["unsub_options_update_listener"] = unsub_options_update_listener
    hass.data[DOMAIN][entry.entry_id] = hass_data
    if bool(hass_data.get("is_rand256")):
        await hass.async_create_task(
            hass.config_entries.async_forward_entry_setups(entry, ["camera", "sensor"])
        )
    else:
        await hass.async_create_task(
            hass.config_entries.async_forward_entry_setups(entry, ["camera"])
        )

    return True


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    if bool(hass.data[DOMAIN][entry.entry_id]["is_rand256"]):
        unload_platform = PLATFORMS
    else:
        unload_platform = [Platform.CAMERA]
    _LOGGER.debug("Platforms to unload: %s", unload_platform)
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, unload_platform
    ):
        # Remove config entry from domain.
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        entry_data["unsub_options_update_listener"]()
        # Remove services
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "reset_trims")
            hass.services.async_remove(DOMAIN, "obstacle_view")
            hass.services.async_remove(DOMAIN, SERVICE_RELOAD)
            await async_remove_vacuums_services(hass)
    return unload_ok


# noinspection PyCallingNonCallable
async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    """Set up the MQTT Camera Custom component from yaml configuration."""

    async def handle_homeassistant_stop(event):
        """Handle Home Assistant stop event."""
        _LOGGER.info("Home Assistant is stopping. Writing down the rooms data.")
        storage = hass.config.path(STORAGE_DIR, CAMERA_STORAGE)
        if not os.path.exists(storage):
            _LOGGER.debug("Storage path: %s do not exists. Aborting!", storage)
            return False
        vacuum_entity_id = await async_get_translations_vacuum_id(storage)
        if not vacuum_entity_id:
            _LOGGER.debug("No vacuum room data found. Aborting!")
            return False
        _LOGGER.debug("Writing down the rooms data for %s.", vacuum_entity_id)
        await async_rename_room_description(hass, vacuum_entity_id)
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


async def async_migrate_entry(hass, config_entry: config_entries.ConfigEntry):
    """Migrate old entry."""
    # as it loads at every rebot, the logs stay in the migration steps
    if config_entry.version == 3.1:
        _LOGGER.debug("Migrating config entry from version %s", config_entry.version)
        old_data = {**config_entry.data}
        new_data = {"vacuum_config_entry": old_data["vacuum_config_entry"]}
        _LOGGER.debug(dict(new_data))
        old_options = {**config_entry.options}
        if len(old_options) != 0:
            tmp_option = {
                "trims_data": {
                    "trim_left": 0,
                    "trim_up": 0,
                    "trim_right": 0,
                    "trim_down": 0,
                },
            }
            new_options = await update_options(old_options, tmp_option)
            _LOGGER.debug("Migration data: %s", dict(new_options))
            hass.config_entries.async_update_entry(
                config_entry, version=3.2, data=new_data, options=new_options
            )
            _LOGGER.info(
                "Migration to config entry version %s successful", config_entry.version
            )
        else:
            _LOGGER.error(
                "Migration failed: No options found in config entry. Please reconfigure the camera."
            )
            return False
    return True

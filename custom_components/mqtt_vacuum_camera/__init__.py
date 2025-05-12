"""
MQTT Vacuum Camera.
Version: 2025.05.0
"""

from functools import partial
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
    LOGGER,
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
from .utils.thread_pool import ThreadPoolManager
from .utils.vacuum.mqtt_vacuum_services import (
    async_register_vacuums_services,
    async_remove_vacuums_services,
    is_rand256_vacuum,
)

PLATFORMS = [Platform.CAMERA, Platform.SENSOR]


async def options_update_listener(hass: core.HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_setup_entry(hass: core.HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""

    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(entry.data)

    # Language cache initialization moved to room_manager.py
    # It now only initializes when needed for room renaming operations
    # This improves performance by avoiding unnecessary initialization

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
        await hass.config_entries.async_forward_entry_setups(
            entry, ["camera", "sensor"]
        )
    else:
        await hass.config_entries.async_forward_entry_setups(entry, ["camera"])

    return True


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    if bool(hass.data[DOMAIN][entry.entry_id]["is_rand256"]):
        unload_platform = PLATFORMS
    else:
        unload_platform = [Platform.CAMERA]
    LOGGER.debug("Platforms to unload: %s", unload_platform)
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, unload_platform
    ):
        # Remove config entry from domain.
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        entry_data["unsub_options_update_listener"]()

        # Shutdown thread pool for this entry
        thread_pool = ThreadPoolManager.get_instance()
        await thread_pool.shutdown(f"{entry.entry_id}_camera")
        await thread_pool.shutdown(f"{entry.entry_id}_camera_text")
        LOGGER.debug("Thread pools for %s shut down", entry.entry_id)

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
        LOGGER.info("Home Assistant is stopping. Writing down the rooms data.")
        storage = hass.config.path(STORAGE_DIR, CAMERA_STORAGE)
        if not os.path.exists(storage):
            LOGGER.debug("Storage path: %s do not exists. Aborting!", storage)
            return False
        vacuum_entity_id = await async_get_translations_vacuum_id(storage)
        if not vacuum_entity_id:
            LOGGER.debug("No vacuum room data found. Aborting!")
            return False
        LOGGER.debug("Writing down the rooms data for %s.", vacuum_entity_id)
        # This will initialize the language cache only when needed
        # The optimization is now handled in room_manager.py
        await async_rename_room_description(hass, vacuum_entity_id)

        # Shutdown all thread pools
        thread_pool = ThreadPoolManager.get_instance()
        await thread_pool.shutdown()
        LOGGER.debug("All thread pools shut down")

        await hass.async_block_till_done()
        return True

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_FINAL_WRITE, handle_homeassistant_stop
    )

    # Make sure MQTT integration is enabled and the client is available
    if not await mqtt.async_wait_for_mqtt_client(hass):
        LOGGER.error("MQTT integration is not available")
        return False
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_migrate_entry(hass, config_entry: config_entries.ConfigEntry):
    """Migrate old entry."""
    # as it loads at every rebot, the logs stay in the migration steps
    if config_entry.version == 3.1:
        LOGGER.debug("Migrating config entry from version %s", config_entry.version)
        old_data = {**config_entry.data}
        new_data = {"vacuum_config_entry": old_data["vacuum_config_entry"]}
        LOGGER.debug(dict(new_data))
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
            LOGGER.debug("Migration data: %s", dict(new_options))
            hass.config_entries.async_update_entry(
                config_entry, version=3.2, data=new_data, options=new_options
            )
            LOGGER.info(
                "Migration to config entry version %s successful", config_entry.version
            )
            return True
    if config_entry.version == 3.2:
        LOGGER.info("Migration to config entry version %s successful", 3.2)
        old_data = {**config_entry.data}
        new_data = {"vacuum_config_entry": old_data["vacuum_config_entry"]}
        LOGGER.debug(dict(new_data))
        old_options = {**config_entry.options}
        if len(old_options) != 0:
            tmp_option = {
                "disable_floor": False,  # Show floor
                "disable_wall": False,  # Show walls
                "disable_robot": False,  # Show robot
                "disable_charger": False,  # Show charger
                "disable_virtual_walls": False,  # Show virtual walls
                "disable_restricted_areas": False,  # Show restricted areas
                "disable_no_mop_areas": False,  # Show no-mop areas
                "disable_obstacles": False,  # Hide obstacles
                "disable_path": False,  # Hide path
                "disable_predicted_path": False,  # Show predicted path
                "disable_go_to_target": False,  # Show go-to target
                "disable_room_1": False,
                "disable_room_2": False,
                "disable_room_3": False,
                "disable_room_4": False,
                "disable_room_5": False,
                "disable_room_6": False,
                "disable_room_7": False,
                "disable_room_8": False,
                "disable_room_9": False,
                "disable_room_10": False,
                "disable_room_11": False,
                "disable_room_12": False,
                "disable_room_13": False,
                "disable_room_14": False,
                "disable_room_15": False,
            }
            new_options = await update_options(old_options, tmp_option)
            LOGGER.debug("Migration data: %s", dict(new_options))
            hass.config_entries.async_update_entry(
                config_entry, version=3.3, data=new_data, options=new_options
            )
            LOGGER.info(
                "Migration to config entry version %s successful",
                config_entry.version,
            )
            return True
        else:
            LOGGER.error(
                "Migration failed: No options found in config entry. Please reconfigure the camera."
            )
            return False
    return True

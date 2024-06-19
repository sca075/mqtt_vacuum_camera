"""valetudo vacuum camera"""

import glob
import logging
import os
import shutil

from homeassistant import config_entries, core
from homeassistant.components import mqtt
from homeassistant.const import (
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    Platform,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.storage import STORAGE_DIR

from .common import (
    get_device_info,
    get_entity_identifier_from_mqtt,
    get_vacuum_mqtt_topic,
    get_vacuum_unique_id_from_mqtt_topic,
    update_options,
)
from .const import (
    CONF_MQTT_HOST,
    CONF_MQTT_PASS,
    CONF_MQTT_USER,
    CONF_VACUUM_CONFIG_ENTRY_ID,
    CONF_VACUUM_CONNECTION_STRING,
    CONF_VACUUM_IDENTIFIERS,
    DOMAIN,
    migrate_me,
)
from .tmp_migrate.migration import (
    async_migrate_entries,  # temporarily import migration function
)
from .utils.users_data import (
    async_get_translations_vacuum_id,
    async_rename_room_description,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CAMERA]


async def options_update_listener(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_migrate_entry(hass, config_entry: config_entries.ConfigEntry):
    """Migrate old entry."""
    mqtt_topic_base = ""
    _LOGGER.debug("Migrating config entry from version %s", config_entry.version)

    if config_entry.version <= 2.0:
        new_data = {**config_entry.data}
        if config_entry.version < 2.0:
            _LOGGER.debug("Migration for integration version 1.4.0 in progress.")
            new_data.pop(CONF_MQTT_HOST, None)
            new_data.pop(CONF_MQTT_USER, None)
            new_data.pop(CONF_MQTT_PASS, None)

            mqtt_topic_base = new_data.pop(CONF_VACUUM_CONNECTION_STRING, None)
            if not mqtt_topic_base:
                _LOGGER.error(
                    "Unable to migrate to config entry version 2.0. Could not find %s. Please recreate this entry.",
                    CONF_VACUUM_CONNECTION_STRING,
                )
                return False

            mqtt_identifier = mqtt_topic_base.split("/")[1]
            config_entry_id = get_entity_identifier_from_mqtt(mqtt_identifier, hass)
            if not config_entry_id:
                _LOGGER.error(
                    "Unable to migrate to config entry version 2.0. Could not find a device for %s."
                    + " Please recreate this entry.",
                    mqtt_topic_base,
                )
                return False
            new_data.update(
                {
                    CONF_VACUUM_CONFIG_ENTRY_ID: config_entry_id,
                }
            )
            _LOGGER.debug("Migrating to config entry version 2.0 completed..")
        _LOGGER.debug("Migration for integration version 1.4.1 in progress.")
        if mqtt_topic_base:
            config_entry.unique_id = get_vacuum_unique_id_from_mqtt_topic(
                mqtt_topic_base
            )
        else:
            config_entry.unique_id = new_data.pop("unique_id", None)
        _LOGGER.debug("Updating unique_id .. to %s", config_entry.unique_id)
        if not config_entry.unique_id:
            _LOGGER.error(
                "Migration Failed, please reconfigure Valetudo Vacuum Camera."
            )
            return False

        new_options = {**config_entry.options}

        keys_to_migrate = [
            "rotate_image",
            "crop_image",
            "trim_top",
            "trim_bottom",
            "trim_left",
            "trim_right",
            "show_vac_status",
            "color_charger",
            "color_move",
            "color_wall",
            "color_robot",
            "color_go_to",
            "color_zone_clean",
            "color_background",
            "color_text",
            "color_no_go",
            "color_room_0",
            "color_room_1",
            "color_room_2",
            "color_room_3",
            "color_room_4",
            "color_room_5",
            "color_room_6",
            "color_room_7",
            "color_room_8",
            "color_room_9",
            "color_room_10",
            "color_room_11",
            "color_room_12",
            "color_room_13",
            "color_room_14",
            "color_room_15",
        ]
        if len(dict(new_options)) == 0:
            new_options.update((k, new_data.pop(k)) for k in keys_to_migrate)

        _LOGGER.debug("Adding Transparency data to the Options..")
        new_options.update(
            {
                "alpha_charger": 255.0,
                "alpha_move": 255.0,
                "alpha_wall": 255.0,
                "alpha_robot": 255.0,
                "alpha_go_to": 255.0,
                "alpha_no_go": 125.0,
                "alpha_zone_clean": 125.0,
                "alpha_background": 255.0,
                "alpha_text": 255.0,
                "alpha_room_0": 255.0,
                "alpha_room_1": 255.0,
                "alpha_room_2": 255.0,
                "alpha_room_3": 255.0,
                "alpha_room_4": 255.0,
                "alpha_room_5": 255.0,
                "alpha_room_6": 255.0,
                "alpha_room_7": 255.0,
                "alpha_room_8": 255.0,
                "alpha_room_9": 255.0,
                "alpha_room_10": 255.0,
                "alpha_room_11": 255.0,
                "alpha_room_12": 255.0,
                "alpha_room_13": 255.0,
                "alpha_room_14": 255.0,
                "alpha_room_15": 255.0,
            }
        )

        config_entry.version = 2.1
        hass.config_entries.async_update_entry(
            config_entry, data=new_data, options=new_options
        )

    if config_entry.version <= 3.0:
        old_data = {**config_entry.data}
        new_data = {"vacuum_config_entry": old_data["vacuum_config_entry"]}
        _LOGGER.debug(dict(new_data))
        old_options = {**config_entry.options}
        if len(old_options) != 0:
            tmp_option = {}
            if config_entry.version == 3.0:
                tmp_option = {
                    "offset_top": 0,
                    "offset_bottom": 0,
                    "offset_left": 0,
                    "offset_right": 0,
                }
            elif config_entry.version < 3:
                tmp_option = {
                    "margins": "100",
                    "auto_zoom": False,
                    "get_svg_file": False,
                    "enable_www_snapshots": True,
                    "aspect_ratio": "None",
                    "zoom_lock_ratio": True,
                    "vac_status_font": "custom_components/valetudo_vacuum_camera/utils/fonts/FiraSans.ttf",
                    "vac_status_size": 50,
                    "vac_status_position": True,
                    "offset_top": 0,
                    "offset_bottom": 0,
                    "offset_left": 0,
                    "offset_right": 0,
                }
                await move_data_to_valetudo_camera(hass.config.path(STORAGE_DIR))

            if tmp_option == {}:
                _LOGGER.error(
                    "Please REMOVE and SETUP the Camera again. Error in migration process!!"
                )
                return False
            new_options = await update_options(old_options, tmp_option)
            _LOGGER.debug(f"migration data:{dict(new_options)}")
            config_entry.version = 3.1
            hass.config_entries.async_update_entry(
                config_entry, data=new_data, options=new_options
            )
        else:
            _LOGGER.error(
                "Please REMOVE and SETUP the Camera again. Error in migration process!!"
            )
            return False

    _LOGGER.info(f"Migration to config entry version successful {config_entry.version}")
    return True


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:

    """Set up platform from a ConfigEntry."""
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

    # Forward the setup to the camera platform.
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "camera")
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
        if len(migrate_me) == 1:
            return await async_migrate_entries(hass)
        else:
            _LOGGER.debug("Home Assistant is stopping. Writing down the rooms data.")
            storage = hass.config.path(STORAGE_DIR, "valetudo_camera")
            _LOGGER.debug(f"Storage path: {storage}")
            vacuum_entity_id = await async_get_translations_vacuum_id(storage)
            if not vacuum_entity_id:
                _LOGGER.debug("No vacuum room data found. Aborting!")
                return True
            _LOGGER.debug(f"Writing down the rooms data for {vacuum_entity_id}.")
            await async_rename_room_description(hass, storage, vacuum_entity_id)
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
        storage_folder = f"{storage}/valetudo_camera"
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

"""
Common functions for the Valetudo Vacuum Camera integration.
Version: 2024.05.4
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from homeassistant.components import mqtt
from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.storage import STORAGE_DIR

_LOGGER: logging.Logger = logging.getLogger(__name__)


def get_device_info(
        config_entry_id: str, hass: HomeAssistant
) -> tuple[str, DeviceEntry] | None:
    """
    Fetches the vacuum's entity ID and Device from the
    entity registry and device registry.
    """
    vacuum_entity_id = er.async_resolve_entity_id(er.async_get(hass), config_entry_id)
    if not vacuum_entity_id:
        _LOGGER.error("Unable to lookup vacuum's entity ID. Was it removed?")
        return None

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    vacuum_device = device_registry.async_get(
        entity_registry.async_get(vacuum_entity_id).device_id
    )

    if not vacuum_device:
        _LOGGER.error("Unable to locate vacuum's device ID. Was it removed?")
        return None

    return vacuum_entity_id, vacuum_device


def get_entity_identifier_from_mqtt(
        mqtt_identifier: str, hass: HomeAssistant
) -> str | None:
    """
    Fetches the vacuum's entity_registry id from the mqtt topic identifier.
    Returns None if it cannot be found.
    """
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(MQTT_DOMAIN, mqtt_identifier)}
    )
    entities = er.async_entries_for_device(entity_registry, device_id=device.id)
    for entity in entities:
        if entity.domain == VACUUM_DOMAIN:
            return entity.id

    return None


def get_vacuum_mqtt_topic(vacuum_entity_id: str, hass: HomeAssistant) -> str | None:
    """
    Fetches the mqtt topic identifier from the MQTT integration. Returns None if it cannot be found.
    """
    try:
        return list(
            mqtt.get_mqtt_data(hass)
            .debug_info_entities.get(vacuum_entity_id)
            .get("subscriptions")
            .keys()
        )[0]
    except AttributeError:
        return None


def get_vacuum_unique_id_from_mqtt_topic(vacuum_mqtt_topic: str) -> str:
    """
    Returns the unique_id computed from the mqtt_topic for the vacuum.
    """
    return vacuum_mqtt_topic.split("/")[1].lower() + "_camera"


async def update_options(bk_options, new_options):
    """
    Keep track of the modified options.
    Returns updated options after editing in Config_Flow.
    version: 1.6.0
    """
    # Initialize updated_options as an empty dictionary
    updated_options = {}

    keys_to_update = [
        "rotate_image",
        "margins",
        "aspect_ratio",
        "offset_top",
        "offset_bottom",
        "offset_left",
        "offset_right",
        "auto_zoom",
        "zoom_lock_ratio",
        "show_vac_status",
        "vac_status_size",
        "vac_status_position",
        "vac_status_font",
        "get_svg_file",
        "enable_www_snapshots",
        "color_charger",
        "color_move",
        "color_wall",
        "color_robot",
        "color_go_to",
        "color_no_go",
        "color_zone_clean",
        "color_background",
        "color_text",
        "alpha_charger",
        "alpha_move",
        "alpha_wall",
        "alpha_robot",
        "alpha_go_to",
        "alpha_no_go",
        "alpha_zone_clean",
        "alpha_background",
        "alpha_text",
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
        "alpha_room_0",
        "alpha_room_1",
        "alpha_room_2",
        "alpha_room_3",
        "alpha_room_4",
        "alpha_room_5",
        "alpha_room_6",
        "alpha_room_7",
        "alpha_room_8",
        "alpha_room_9",
        "alpha_room_10",
        "alpha_room_11",
        "alpha_room_12",
        "alpha_room_13",
        "alpha_room_14",
        "alpha_room_15",
    ]
    try:
        for key in keys_to_update:
            if key in new_options:
                updated_options[key] = new_options[key]
            else:
                updated_options[key] = bk_options[key]
    except KeyError as e:
        _LOGGER.warning(f"Error in migrating options, please re-setup the camera: {e}")
        return bk_options
    # updated_options is a dictionary containing the merged options
    updated_bk_options = updated_options  # or backup_options, as needed
    return updated_bk_options


async def async_find_last_logged_in_user(hass: HomeAssistant) -> Optional[str]:
    """Search and return the last logged-in user ID."""
    file_path = f"{hass.config.path(STORAGE_DIR)}/auth"
    try:
        with open(file_path) as file:
            data = json.load(file)

    except FileNotFoundError:
        _LOGGER.info("User ID File not found: %s", file_path)
        return None

    # Check if the data is not empty
    if isinstance(data, dict) and data:
        # Return the last entry
        last_one = len(list(data['data']['refresh_tokens']))-1
        last_user_id = (str(data['data']['refresh_tokens'][last_one]['user_id']))
        return last_user_id


async def async_get_active_user_id(hass: HomeAssistant) -> Optional[str]:
    """
    Get the active user id from the frontend user data file.
    Return the language of the active user.
    """
    ha_language = hass.config.language.lower()  # testing
    active_user_id = await async_find_last_logged_in_user(hass)
    file_path = f"{hass.config.path(STORAGE_DIR)}/frontend.user_data_{active_user_id}"
    try:
        with open(file_path) as file:
            data = json.load(file)
            language = data["data"]["language"]["language"]
            return language
    except FileNotFoundError:
        _LOGGER.info("User ID File not found: %s", file_path)
        return "en"
    except KeyError:
        _LOGGER.info("User ID Language not found: %s", file_path)
        return "en"


def load_language(storage_path: str) -> str:
    """Load the selected language from the language.json file."""
    language_file_path = os.path.join(storage_path, "language.json")
    try:
        with open(language_file_path) as language_file:
            data = json.load(language_file)
            selected_language = data.get("language", {}).get("selected", "")
            return selected_language
    except FileNotFoundError:
        _LOGGER.warning(
            f"Language file not found in {storage_path}. "
            f"The file will be stored as soon the vacuum is operated"
        )
        return ""
    except json.JSONDecodeError:
        _LOGGER.error("Error decoding language file.")
        return ""


def load_translations_json(hass, language: str) -> json:
    """
    Load the user selected language json file and return it.
    @param hass: Home Assistant instance.
    @param language:self.hass.config.path(f"custom_components/valetudo_vacuum_camera/translations/
    @return: json format
    """
    translations_path = hass.config.path(
        f"custom_components/valetudo_vacuum_camera/translations"
    )
    file_name = f"{language}.json"
    file_path = f"{translations_path}/{file_name}"
    try:
        with open(file_path) as file:
            translations = json.load(file)
    except FileNotFoundError:
        return None
    return translations


async def async_load_room_data(storage_path: str, vacuum_id: str) -> dict:
    """Load the room data from the room_data_{vacuum_id}.json file."""
    data_file_path = os.path.join(storage_path, f"room_data_{vacuum_id}.json")
    try:
        with open(data_file_path) as data_file:
            data = json.load(data_file)
            return data
    except FileNotFoundError:
        _LOGGER.warning(
            f"Room data file not found: {data_file_path}, "
            f"the file will be created as soon the segment clean will be operated"
        )
        return {}
    except json.JSONDecodeError:
        _LOGGER.error(f"Error decoding room data file: {data_file_path}")
        return {}


async def rename_room_description(
        hass: HomeAssistant, storage_path: str, vacuum_id: str
) -> None:
    """
    Add room names to the room descriptions in the translations.
    """
    language = load_language(storage_path)
    edit_path = hass.config.path(
        f"custom_components/valetudo_vacuum_camera/translations/{language}.json"
    )
    _LOGGER.info(f"Editing the translations file: {edit_path}")
    data = load_translations_json(hass, language)
    if data is None:
        _LOGGER.warning(
            f"Translation for {language} not found."
            " Please report the missing translation to the author."
        )
        data = load_translations_json(hass, "en")
    room_data = await async_load_room_data(storage_path, vacuum_id)

    # Modify the "data_description" keys for rooms_colours_1 and rooms_colours_2
    for i in range(1, 3):
        room_key = f"rooms_colours_{i}"
        start_index = 0 if i == 1 else 8
        end_index = 8 if i == 1 else 16
        for j in range(start_index, end_index):
            if j < len(room_data):
                room_id, room_info = list(room_data.items())[j]
                data["options"]["step"][room_key]["data_description"][
                    f"color_room_{j}"
                ] = f"**RoomID {room_id} {room_info['name']}**"

    # Modify the "data" keys for alpha_2 and alpha_3
    for i in range(2, 4):
        alpha_key = f"alpha_{i}"
        start_index = 0 if i == 2 else 8
        end_index = 8 if i == 2 else 16
        for j in range(start_index, end_index):
            if j < len(room_data):
                room_id, room_info = list(room_data.items())[j]
                data["options"]["step"][alpha_key]["data"][
                    f"alpha_room_{j}"
                ] = f"RoomID {room_id} {room_info['name']}"
                # "**text**" is bold as in markdown

    # Write the modified data back to the JSON file
    with open(edit_path, "w") as file:
        json.dump(data, file, indent=2)
    _LOGGER.info("Room names added to the room descriptions in the translations.")
    return None

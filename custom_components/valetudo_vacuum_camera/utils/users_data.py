"""
Common functions for the Valetudo Vacuum Camera integration.
Those functions are used to store and retrieve user data from the Home Assistant storage.
The data will be stored locally in the Home Assistant in .storage/valetudo_camera directory.
Author: @sca075
Version: 2024.06.0
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR

_LOGGER: logging.Logger = logging.getLogger(__name__)


def is_auth_updated(self) -> bool:
    """Check if the auth file has been updated."""
    file_path = self.hass.config.path(STORAGE_DIR, "auth")
    # Get the last modified time of the file
    last_modified_time = os.path.getmtime(file_path)
    if self._update_time is None:
        self._update_time = last_modified_time
        return True
    elif self._update_time == last_modified_time:
        return False
    elif self._update_time < last_modified_time:
        self._update_time = last_modified_time
        return True


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
        last_one = len(list(data["data"]["refresh_tokens"])) - 1
        last_user_id = str(data["data"]["refresh_tokens"][last_one]["user_id"])
        return last_user_id


async def async_get_user_ids(hass: HomeAssistant) -> list[str]:
    """Get the user IDs from the auth file."""
    file_path = f"{hass.config.path(STORAGE_DIR)}/auth"
    # Load the JSON data
    try:
        with open(file_path) as file:
            data = json.load(file)

    except FileNotFoundError:
        _LOGGER.info("File not found: %s", file_path)
        return []

    # Extract user IDs for users other than "Supervisor" and "Home Assistant Content"
    user_ids = [
        user["id"]
        for user in data["data"]["users"]
        if user["name"] not in ["Supervisor", "Home Assistant Content"]
    ]
    return user_ids


async def async_get_active_user_language(hass: HomeAssistant) -> Optional[str]:
    """
    Get the active user id from the frontend user data file.
    Return the language of the active user.
    """
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


async def async_write_languages_json(hass: HomeAssistant):
    """
    Write the languages.json file with languages for all users.
    """
    try:
        user_ids = await async_get_user_ids(hass)
        storage_path = hass.config.path(STORAGE_DIR)
        languages = {"languages": []}
        for user_id in user_ids:
            file_path = f"{storage_path}/frontend.user_data_{user_id}"
            try:
                with open(file_path) as file:
                    data = json.load(file)
                    language = data["data"]["language"]["language"]
                    languages["languages"].append(
                        {"user_id": user_id, "language": language}
                    )
            except FileNotFoundError:
                _LOGGER.info("User ID File not found: %s", file_path)
                continue
            except KeyError:
                _LOGGER.info("User ID Language not found: %s", file_path)
                continue
        file_path = os.path.join(storage_path, "valetudo_camera", "languages.json")
        with open(file_path, "w") as outfile:
            json.dump(languages, outfile)
    except Exception as e:
        _LOGGER.error("Error writing languages.json: %s", str(e))


async def async_load_language(storage_path: str, selected_languages=None) -> list:
    """Load the selected language from the language.json file."""
    if selected_languages is None:
        selected_languages = []
    language_file_path = os.path.join(storage_path, "languages.json")
    try:
        with open(language_file_path) as language_file:
            data = json.load(language_file)
            # Access the "languages" key first
            languages = data.get("languages", [])
            # Extract language from each dictionary
            for lang_data in languages:
                language = lang_data.get("language", "")
                selected_languages.append(language)
            return selected_languages
    except FileNotFoundError:
        # Handle case where language file is not found
        _LOGGER.warning(
            f"Language file not found in {storage_path}. "
            f"The file will be stored as soon as the vacuum is operated."
        )
        return []
    except json.JSONDecodeError:
        # Handle case where JSON decoding error occurs
        _LOGGER.error("Error decoding language file.")
        return []


async def async_load_translations_json(
    hass: HomeAssistant, languages: list[str]
) -> list[Optional[dict]]:
    """
    Load the user selected language json files and return them as a list of JSON objects.
    @param hass: Home Assistant instance.
    @param languages: List of languages to load.
    @return: List of JSON objects containing translations for each language.
    """
    translations_list = []
    translations_path = hass.config.path(
        "custom_components/valetudo_vacuum_camera/translations"
    )

    for language in languages:
        file_name = f"{language}.json"
        file_path = f"{translations_path}/{file_name}"

        try:
            with open(file_path) as file:
                translations = json.load(file)
                translations_list.append(translations)
        except FileNotFoundError:
            translations_list.append(None)

    return translations_list


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


async def async_rename_room_description(
    hass: HomeAssistant, storage_path: str, vacuum_id: str
) -> None:
    """
    Add room names to the room descriptions in the translations.
    """
    language = await async_load_language(storage_path)
    edit_path = hass.config.path(
        f"custom_components/valetudo_vacuum_camera/translations"
    )
    _LOGGER.info(f"Editing the translations file for language: {language}")
    data_list = await async_load_translations_json(hass, language)

    if None in data_list:
        _LOGGER.warning(
            f"Translation for {language} not found."
            " Please report the missing translation to the author."
        )
        data_list = await async_load_translations_json(hass, ["en"])

    room_data = await async_load_room_data(storage_path, vacuum_id)

    # Modify the "data_description" keys for rooms_colours_1 and rooms_colours_2
    for data in data_list:
        if data is None:
            continue
        for i in range(1, 3):
            room_key = f"rooms_colours_{i}"
            start_index = 0 if i == 1 else 8
            end_index = 8 if i == 1 else 16
            for j in range(start_index, end_index):
                if j < len(room_data):
                    room_id, room_info = list(room_data.items())[j]
                    data["options"]["step"][room_key]["data_description"][
                        f"color_room_{j}"
                    ] = f"### **RoomID {room_id} {room_info['name']}**"

    # Modify the "data" keys for alpha_2 and alpha_3
    for data in data_list:
        if data is None:
            continue
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

    # Write the modified data back to the JSON files
    for idx, data in enumerate(data_list):
        if data is not None:
            with open(os.path.join(edit_path, f"{language[idx]}.json"), "w") as file:
                json.dump(data, file, indent=2)
            _LOGGER.info(
                "Room names added to the room descriptions in the translations."
            )
    return None

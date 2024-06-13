"""
Users Data for the Valetudo Vacuum Camera integration.
Those functions are used to store and retrieve user data from the Home Assistant storage.
The data will be stored locally in the Home Assistant in .storage/valetudo_camera directory.
Author: @sca075
Version: 2024.06.4
"""

from __future__ import annotations

import glob
import json
import logging
import os
from typing import Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR

from custom_components.valetudo_vacuum_camera.common import (
    async_load_file,
    async_write_json_to_disk,
)
from custom_components.valetudo_vacuum_camera.const import DEFAULT_ROOMS

_LOGGER: logging.Logger = logging.getLogger(__name__)


async def async_get_rooms_count(
    robot_name: str,
) -> int:
    """Get the number of segments in the room_data_{vacuum_id}.json file."""
    file_path = os.path.join(
        os.getcwd(), STORAGE_DIR, "valetudo_camera", f"room_data_{robot_name}.json"
    )
    if not os.path.exists(file_path):
        _LOGGER.warning(f"File not found: {file_path}")
        return DEFAULT_ROOMS
    else:
        room_data = await async_load_file(file_path, True)
        if room_data:
            room_count = room_data.get("segments", DEFAULT_ROOMS)
            return room_count
        else:
            _LOGGER.error(f"Error decoding file: {file_path}")
            return DEFAULT_ROOMS


async def async_write_vacuum_id(storage_dir, vacuum_id):
    """Write the vacuum_id to a JSON file."""
    # Create the full file path
    json_path = os.path.join(storage_dir, "rooms_colours_description.json")
    # Data to be written
    data = {"vacuum_id": vacuum_id}
    # Write data to a JSON file
    await async_write_json_to_disk(json_path, data)
    _LOGGER.info(f"vacuum_id saved: {vacuum_id}")


async def async_get_translations_vacuum_id(storage_dir):
    """Read the vacuum_id from a JSON file."""
    # Create the full file path
    vacuum_id_path = os.path.join(storage_dir, "rooms_colours_description.json")
    try:
        data = await async_load_file(vacuum_id_path, True)
        vacuum_id = data.get("vacuum_id", None)
        return vacuum_id
    except json.JSONDecodeError:
        _LOGGER.warning(f"Error reading the file {vacuum_id_path}.")
    except OSError as e:
        _LOGGER.error(f"Unhandled exception: {e}")
        return None


def remove_room_data_files(directory: str) -> None:
    """Remove all 'room_data*.json' files in the specified directory."""
    # Create the full path pattern for glob to match
    path_pattern = os.path.join(directory, "room_data*.json")
    # Find all files matching the pattern
    files = glob.glob(path_pattern)
    if not files:
        _LOGGER.debug(f"No files found matching pattern: {path_pattern}")
        return
    # Loop through and remove each file
    for file in files:
        try:
            os.remove(file)
            _LOGGER.debug(f"Removed file: {file}")
        except OSError as e:
            _LOGGER.debug(f"Error removing file {file}: {e}")


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


async def async_find_last_logged_in_user(hass: HomeAssistant) -> str or None:
    """Retrieve the ID of the last logged-in user based on the most recent token usage."""
    users = await hass.auth.async_get_users()  # Fetches list of all user objects
    last_user = None
    last_login_time = None

    # Iterate through users to find the one with the most recent activity
    for user in users:
        # Iterate through refresh tokens to find the most recent usage
        for token in user.refresh_tokens.values():
            if token.last_used_at and (
                last_login_time is None or token.last_used_at > last_login_time
            ):
                last_login_time = token.last_used_at
                last_user = user

    if last_user:
        _LOGGER.info(f"Last logged-in user: {last_user.id}")
        return last_user.id
    else:
        _LOGGER.info("No users have logged in yet.")
        return None


async def async_get_user_ids(hass: HomeAssistant) -> list[str]:
    """Get the user IDs, excluding certain system users."""
    users = await hass.auth.async_get_users()
    excluded_users = ["Supervisor", "Home Assistant Content", "Home Assistant Cloud"]

    # Filter out users based on their name not being in the excluded list
    user_ids = [user.id for user in users if user.name not in excluded_users]

    return user_ids


async def async_get_active_user_language(hass: HomeAssistant) -> str:
    """
    Retrieve the language of the last logged-in user from languages.json.
    If the user's language setting is not found, default to English.
    """
    active_user_id = await async_find_last_logged_in_user(hass)
    languages_path = f"{hass.config.path(STORAGE_DIR)}/valetudo_camera/languages.json"
    user_data_path = hass.config.path(
        STORAGE_DIR, f"frontend.user_data_{active_user_id}"
    )
    if os.path.exists(languages_path):
        languages_file = await async_load_file(languages_path)
        if languages_file:
            languages_data = json.loads(languages_file)
            for language_info in languages_data.get("languages", []):
                if language_info.get("user_id") == active_user_id:
                    return language_info.get("language", "en")
        else:
            _LOGGER.info(
                "Cannot load languages.json file. Defaulting to English language."
            )
            return "en"
    elif os.path.exists(user_data_path):
        user_data_file = await async_load_file(user_data_path)
        try:
            if user_data_file:
                data = json.loads(user_data_file)
                language = data["data"]["language"]["language"]
                return language
            else:
                raise KeyError
        except KeyError:
            return "en"

    else:
        _LOGGER.info("Defaulting to English language.")
        return "en"


async def async_write_languages_json(hass: HomeAssistant):
    """
    Write the languages.json file with languages for all users excluding system accounts.
    """
    try:
        user_ids = await async_get_user_ids(hass)  # This function exclude system users
        _LOGGER.info(f"Saving User IDs: {user_ids} languages...")
        languages = {"languages": []}
        for user_id in user_ids:
            user_data_file = hass.config.path(
                STORAGE_DIR, f"frontend.user_data_{user_id}"
            )

            if os.path.exists(user_data_file):
                user_data = await async_load_file(user_data_file)
                try:
                    data = json.loads(user_data)
                    language = data["data"]["language"]["language"]
                    languages["languages"].append(
                        {"user_id": user_id, "language": language}
                    )
                except KeyError:
                    raise KeyError
                except json.JSONDecodeError:
                    raise json.JSONDecodeError
                else:
                    _LOGGER.info(f"User ID: {user_id}, language: {language}")
            else:
                _LOGGER.info(f"User ID: {user_id}, skipping...")
                return None

        # Write the consolidated languages to a JSON file
        out_languages_file = hass.config.path(
            STORAGE_DIR, "valetudo_camera", "languages.json"
        )
        await async_write_json_to_disk(out_languages_file, languages)

    except Exception as e:
        _LOGGER.warning(f"Error while writing languages.json: {str(e)}")


async def async_load_languages(storage_path: str, selected_languages=None) -> list:
    """Load the selected language from the language.json file."""
    if selected_languages is None:
        selected_languages = []
    language_file_path = os.path.join(storage_path, "languages.json")
    if os.path.exists(language_file_path):
        language_file = await async_load_file(language_file_path)
        if language_file:
            try:
                languages_data = json.loads(language_file)
            except json.JSONDecodeError:
                _LOGGER.error(f"Error decoding language file: {language_file_path}")
                return []
            for language_info in languages_data.get("languages", []):
                language = language_info.get("language", "")
                selected_languages.append(language)
            return selected_languages
        else:
            _LOGGER.warning(f"Language file not found in {storage_path}.")
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
        _LOGGER.debug(f"Loading translations for language: {language}")
        locals_file_name = f"{language}.json"
        locals_file_path = f"{translations_path}/{locals_file_name}"

        try:
            translations = await async_load_file(locals_file_path, True)
            translations_list.append(translations)
        except FileNotFoundError:
            translations_list.append(None)

    return translations_list


async def async_load_room_data(storage_path: str, vacuum_id: str) -> dict:
    """Load the room data from the room_data_{vacuum_id}.json file."""
    data_file_path = os.path.join(storage_path, f"room_data_{vacuum_id}.json")
    if os.path.exists(data_file_path):
        data = await async_load_file(data_file_path, True)
        _LOGGER.debug(f"Room data loaded from: {data_file_path}")
        return data
    else:
        _LOGGER.debug(f"File not found: {data_file_path}")
        return {}


async def async_rename_room_description(
    hass: HomeAssistant, storage_path: str, vacuum_id: str
) -> None:
    """
    Add room names to the room descriptions in the translations.
    """
    room_json = await async_load_room_data(storage_path, vacuum_id)
    room_data = room_json.get("rooms", {})

    if not room_json:
        _LOGGER.warning(
            f"Vacuum ID: {vacuum_id} do not support Rooms! Aborting room name addition."
        )
        return None

    # Save the vacuum_id to a JSON file
    await async_write_vacuum_id(storage_path, vacuum_id)
    # Get the languages to modify
    language = await async_load_languages(storage_path)
    _LOGGER.info(f"Languages to modify: {language}")
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
            await async_write_json_to_disk(
                os.path.join(edit_path, f"{language[idx]}.json"), data
            )
            _LOGGER.info(
                f"Room names added to the room descriptions in the {language[idx]} translations."
            )
    return None

"""
files_operations.py
Common functions for the MQTT Vacuum Camera integration.
Those functions are used to store and retrieve user data from the Home Assistant storage.
The data will be stored locally in the Home Assistant in .storage/valetudo_camera directory.
Author: @sca075
Version: 2025.3.0b0
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import glob
import json
import os
import re
from typing import Any, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.storage import STORAGE_DIR

from ..const import CAMERA_STORAGE, LOGGER
from .language_cache import LanguageCache
from .room_manager import RoomManager


async def async_write_vacuum_id(
    hass: HomeAssistant, file_name: str, vacuum_id: str
) -> None:
    """Write the vacuum_id to a JSON file."""
    # Create the full file path
    if vacuum_id:
        json_path = f"{hass.config.path(STORAGE_DIR, CAMERA_STORAGE)}/{file_name}"
        LOGGER.debug("Writing vacuum_id: %s to %s", vacuum_id, json_path)
        # Data to be written
        data = {"vacuum_id": vacuum_id}
        # Write data to a JSON file
        await async_write_json_to_disk(json_path, data)
        if os.path.exists(json_path):
            LOGGER.info("vacuum_id saved: %s", vacuum_id)
        else:
            LOGGER.warning("Error saving vacuum_id: %s", vacuum_id, exc_info=True)
    else:
        LOGGER.warning("No vacuum_id provided.")


async def async_get_translations_vacuum_id(storage_dir: str) -> Optional[str]:
    """Read the vacuum_id from a JSON file."""
    # Create the full file path
    vacuum_id_path = os.path.join(storage_dir, "rooms_colours_description.json")
    try:
        data = await async_load_file(vacuum_id_path, True)
        if data is None:
            return None
        return data.get("vacuum_id", None)
    except json.JSONDecodeError:
        LOGGER.warning("Error reading the file %s.", vacuum_id_path, exc_info=True)
        return None
    except OSError as e:
        LOGGER.error("Unhandled exception: %s", e, exc_info=True)
        return None


def remove_room_data_files(directory: str) -> None:
    """Remove all 'room_data*.json' files in the specified directory."""
    # Create the full path pattern for glob to match
    path_pattern = os.path.join(directory, "room_data*.json")
    # Find all files matching the pattern
    files = glob.glob(path_pattern)
    if not files:
        LOGGER.debug("No files found matching pattern: %s", path_pattern)
        return
    # Loop through and remove each file
    for file in files:
        try:
            os.remove(file)
            LOGGER.debug("Removed file: %s", file)
        except OSError as e:
            LOGGER.debug("Error removing file %s: %r", file, e, exc_info=True)


def is_auth_updated(self) -> bool:
    """Check if the auth file has been updated."""
    file_path = self.hass.config.path(STORAGE_DIR, "auth")
    # Get the last modified time of the file
    last_modified_time = os.path.getmtime(file_path)
    if self.auth_update_time is None:
        self.auth_update_time = last_modified_time
        return True
    if self.auth_update_time == last_modified_time:
        return False
    if self.auth_update_time < last_modified_time:
        self.auth_update_time = last_modified_time
        return True
    return False  # Default case


async def async_find_last_logged_in_user(hass: HomeAssistant) -> Optional[str]:
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
        return last_user.id
    LOGGER.info("No users have logged in yet.")
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
    Retrieve the language of the last logged-in user using the language cache.
    If the user's language setting is not found, default to English.
    """
    # Use the language cache to avoid repeated I/O operations
    language_cache = LanguageCache.get_instance()

    # Initialize the cache if needed
    # Use a property or method to check initialization status instead of accessing protected member
    if (
        not hasattr(language_cache, "is_initialized")
        or not language_cache.is_initialized()
    ):
        await language_cache.initialize(hass)

    # Get the language from the cache
    return await language_cache.get_active_user_language(hass)


async def async_load_languages(selected_languages=None) -> list:
    """
    Load the selected languages from the language cache.
    """
    if selected_languages is None:
        selected_languages = []

    # Use the language cache to avoid repeated I/O operations
    language_cache = LanguageCache.get_instance()
    try:
        all_languages = await language_cache.get_all_languages()
        if all_languages:
            selected_languages.extend(all_languages)
    except Exception as e:
        LOGGER.warning("Error while loading languages: %s", str(e), exc_info=True)

    return selected_languages


async def async_populate_user_languages(hass: HomeAssistant):
    """
    Populate the language cache with languages for all users excluding system accounts.
    """
    try:
        # Use the language cache to avoid repeated I/O operations
        language_cache = LanguageCache.get_instance()

        # Initialize the cache if needed
        if not language_cache.is_initialized():
            await language_cache.initialize(hass)
            LOGGER.info("Language cache initialized.")
        else:
            LOGGER.info("Language cache already initialized.")
    except Exception as e:
        LOGGER.warning(
            "Error while initializing language cache: %s", str(e), exc_info=True
        )


async def async_load_translations_json(
    hass: HomeAssistant, languages: list[str]
) -> list[Optional[dict]]:
    """
    Load the user selected language json files and return them as a list of JSON objects.
    Uses the language cache to reduce I/O operations.
    """
    # Use the language cache to avoid repeated I/O operations
    language_cache = LanguageCache.get_instance()

    # Load translations from the cache
    return await language_cache.load_translations_json(hass, languages)


async def async_rename_room_description(hass: HomeAssistant, vacuum_id: str) -> bool:
    """
    Add room names to the room descriptions in the translations.
    Uses the optimized RoomManager to reduce I/O operations.
    """
    # Use the RoomManager to handle room operations with optimized I/O
    room_manager = RoomManager(hass)

    # Perform the room renaming with optimized I/O
    return await room_manager.rename_room_descriptions(vacuum_id)


async def async_del_file(file):
    """Delete a file if it exists."""
    if os.path.exists(file):
        LOGGER.info("Removing the file %s", file)
        os.remove(file)
    else:
        LOGGER.debug("File not found: %s", file)


async def async_write_file_to_disk(
    file_to_write: str, data, is_binary: bool = False
) -> None:
    """
    Asynchronously write data to a file.
    """

    def _write_to_file(file_path, data_to_write, binary_mode):
        """Helper function to write data to a file."""
        if binary_mode:
            with open(file_path, "wb") as datafile:
                datafile.write(data_to_write)
        else:
            with open(file_path, "w") as datafile:
                datafile.write(data_to_write)

    try:
        await asyncio.to_thread(_write_to_file, file_to_write, data, is_binary)
    except (OSError, IOError) as e:
        LOGGER.warning("Error on writing data to disk.: %s", e, exc_info=True)
    except Exception as e:
        LOGGER.warning("Unexpected issue detected: %s", e, exc_info=True)


async def async_write_json_to_disk(file_to_write: str, json_data) -> None:
    """Asynchronously write data to a JSON file."""

    def _write_to_file(file_path, data):
        """Helper function to write data to a file."""
        with open(file_path, "w") as datafile:
            json.dump(data, datafile, indent=2)

    try:
        await asyncio.to_thread(_write_to_file, file_to_write, json_data)
    except (OSError, IOError, json.JSONDecodeError) as e:
        LOGGER.warning("Json File Operation Error: %s", e, exc_info=True)
    except Exception as e:
        LOGGER.warning("Unexpected issue detected: %s", e, exc_info=True)


async def async_load_file(file_to_load: str, is_json: bool = False) -> Any:
    """Asynchronously load JSON data from a file."""

    def read_file(my_file: str, read_json: bool = False):
        """Helper function to read data from a file."""
        try:
            if read_json:
                with open(my_file) as file:
                    return json.load(file)
            else:
                with open(my_file) as file:
                    return file.read()
        except (FileNotFoundError, json.JSONDecodeError):
            LOGGER.warning("%s does not exist.", my_file, exc_info=True)
            return None

    try:
        return await asyncio.to_thread(read_file, file_to_load, is_json)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        LOGGER.warning("Blocking IO issue detected: %s", e, exc_info=True)
        return None


def extract_core_entity_ids(entity_ids: list[str]) -> list[str]:
    """
    Extracts the core part of the entity IDs.
    """
    core_entity_ids = []
    for entity_id in entity_ids:
        if entity_id.startswith("camera."):
            core_id = entity_id.split("camera.")[1]
            # Strip known prefixes and suffixes
            core_id = re.sub(r"^(valetudo_[^_]*_)?(.*?)(_camera)?$", r"\2", core_id)
            core_entity_ids.append(core_id)
    return core_entity_ids


async def async_list_files(pattern: str) -> List[str]:
    """List files matching the pattern asynchronously."""
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(pool, glob.glob, pattern)


async def get_trims_files_names(path: str, entity_ids: list[str]) -> list[str]:
    """
    Generates the list of file names to delete based on the core entity IDs.
    """
    core_entity_ids = extract_core_entity_ids(entity_ids)
    file_names = [f"{path}/auto_crop_{core_id}.json" for core_id in core_entity_ids]
    return file_names


async def async_clean_up_all_auto_crop_files(hass: HomeAssistant) -> None:
    """
    Deletes all auto_crop_*.json files in the specified directory.
    """

    directory = hass.config.path(STORAGE_DIR, CAMERA_STORAGE)
    # Create the pattern to match all auto_crop_*.json files
    pattern = os.path.join(directory, "auto_crop_*.json")
    # List all matching files
    files_to_delete = await async_list_files(pattern)
    # Iterate over the files and delete each one
    for file_path in files_to_delete:
        try:
            os.remove(file_path)
            print(f"Deleted: {file_path}")
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")


async def async_reset_map_trims(hass: HomeAssistant, entity_list: list) -> bool:
    """
    Reset the map trims.
    """
    if not entity_list:
        LOGGER.debug("No entity IDs provided.")
        raise ServiceValidationError("no_entity_id_provided")
    LOGGER.debug("Resetting the map trims.")
    files_path = hass.config.path(STORAGE_DIR, CAMERA_STORAGE)

    # Collect files to delete
    files_to_delete = await get_trims_files_names(files_path, entity_list)

    # Loop through the list of files and remove each one asynchronously
    if not files_to_delete:
        LOGGER.debug("No files found to delete.")
        return False

    for file_path in files_to_delete:
        await async_del_file(file_path)

    return True

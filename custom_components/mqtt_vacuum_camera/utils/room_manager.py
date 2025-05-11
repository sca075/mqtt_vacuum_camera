"""
Room Manager for MQTT Vacuum Camera.
This module provides optimized room renaming operations.
Version: 2025.5.0
"""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
import json
import logging
import os
from typing import List, Optional, Tuple

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR
from valetudo_map_parser.config.types import RoomStore

from ..const import CAMERA_STORAGE
from .language_cache import LanguageCache

_LOGGER = logging.getLogger(__name__)


@dataclass
class RoomInfo:
    """Class to store room information."""

    room_id: str
    name: str

    @classmethod
    def from_dict(cls, room_id: str, data: dict) -> RoomInfo:
        """Create a RoomInfo instance from a dictionary."""
        return cls(room_id=room_id, name=data.get("name", f"Room {room_id}"))


class RoomManager:
    """
    A class that manages room operations with optimized I/O.
    """

    def __init__(self, hass: HomeAssistant):
        """Initialize the RoomManager."""
        self.hass = hass
        self.language_cache = LanguageCache.get_instance()

    async def write_vacuum_id(self, vacuum_id: str) -> None:
        """
        Write the vacuum_id to a JSON file.

        Args:
            vacuum_id: The vacuum ID to write
        """
        if not vacuum_id:
            _LOGGER.warning("No vacuum_id provided.")
            return

        json_path = f"{self.hass.config.path(STORAGE_DIR, CAMERA_STORAGE)}/rooms_colours_description.json"
        _LOGGER.debug("Writing vacuum_id: %s to %s", vacuum_id, json_path)

        # Data to be written
        data = {"vacuum_id": vacuum_id}

        # Write data to a JSON file
        try:
            await asyncio.to_thread(
                os.makedirs, os.path.dirname(json_path), exist_ok=True
            )
            await self._write_json_file(json_path, data)

            if await asyncio.to_thread(os.path.exists, json_path):
                _LOGGER.info("vacuum_id saved: %s", vacuum_id)
            else:
                _LOGGER.warning("Error saving vacuum_id: %s", vacuum_id)
        except Exception as e:
            _LOGGER.warning("Error writing vacuum_id: %s", str(e), exc_info=True)

    async def rename_room_descriptions(self, vacuum_id: str) -> bool:
        """
        Add room names to the room descriptions in the translations.
        This is an optimized version that reduces I/O operations.

        Args:
            vacuum_id: The vacuum ID

        Returns:
            True if successful, False otherwise
        """
        # Load the room data
        rooms = RoomStore(vacuum_id)
        room_data = rooms.get_rooms()

        if not room_data:
            _LOGGER.warning(
                "Vacuum ID: %s does not support Rooms! Aborting room name addition.",
                vacuum_id,
            )
            return False

        # Save the vacuum_id to a JSON file
        await self.write_vacuum_id(vacuum_id)

        # Initialize the language cache if needed - only during room renaming
        if not self.language_cache.is_initialized():
            await self.language_cache.initialize(self.hass)
            _LOGGER.info("Language cache initialized for room renaming")

        # Get the languages to modify
        languages = await self.language_cache.get_all_languages()
        if not languages:
            languages = ["en"]

        edit_path = self.hass.config.path(
            "custom_components/mqtt_vacuum_camera/translations"
        )
        _LOGGER.info("Editing the translations file for languages: %s", languages)

        # Load all translation files in one batch
        data_list = await self.language_cache.load_translations_json(
            self.hass, languages
        )

        # If any translations are missing, fall back to English
        if None in data_list:
            _LOGGER.warning(
                "Translation for some languages not found. Falling back to English."
            )
            en_translation = await self.language_cache.load_translation(self.hass, "en")
            if en_translation:
                # Replace None values with English translation
                data_list = [
                    data if data is not None else en_translation for data in data_list
                ]

        # Process room data
        room_list = list(room_data.items())

        # Batch all modifications to reduce I/O
        modifications = []

        for idx, data in enumerate(data_list):
            if data is None:
                continue

            lang = languages[idx] if isinstance(languages, list) else languages
            modified_data = await self._modify_translation_data(data, room_list)

            if modified_data:
                modifications.append((lang, modified_data))

        # Write all modified files in one batch
        tasks = []
        for lang, data in modifications:
            file_path = os.path.join(edit_path, f"{lang}.json")
            tasks.append(self._write_json_file(file_path, data))

        if tasks:
            await asyncio.gather(*tasks)
            _LOGGER.info(
                "Room names added to the room descriptions in %d translations.",
                len(tasks),
            )

        return True

    @staticmethod
    async def _modify_translation_data(
        data: dict, room_list: List[Tuple[str, dict]]
    ) -> Optional[dict]:
        """
        Modify translation data with room information.

        Args:
            data: The translation data
            room_list: List of room information tuples

        Returns:
            Modified translation data or None if no modifications
        """
        if data is None:
            return None

        # Make a deep copy to avoid mutating the cached object
        modified_data = copy.deepcopy(data)

        # Ensure the base structure exists
        options = modified_data.setdefault("options", {})
        step = options.setdefault("step", {})

        # Default room colors from en.json
        default_room_colors = {
            "color_room_0": "[135, 206, 250]",  # Floor/Room 1
            "color_room_1": "[176, 226, 255]",  # Room 2
            "color_room_2": "[165, 105, 18]",  # Room 3
            "color_room_3": "[164, 211, 238]",  # Room 4
            "color_room_4": "[141, 182, 205]",  # Room 5
            "color_room_5": "[96, 123, 139]",  # Room 6
            "color_room_6": "[224, 255, 255]",  # Room 7
            "color_room_7": "[209, 238, 238]",  # Room 8
            "color_room_8": "[180, 205, 205]",  # Room 9
            "color_room_9": "[122, 139, 139]",  # Room 10
            "color_room_10": "[175, 238, 238]",  # Room 11
            "color_room_11": "[84, 153, 199]",  # Room 12
            "color_room_12": "[133, 193, 233]",  # Room 13
            "color_room_13": "[245, 176, 65]",  # Room 14
            "color_room_14": "[82, 190, 128]",  # Room 15
            "color_room_15": "[72, 201, 176]",  # Room 16
        }

        # Default room descriptions
        default_room_descriptions = {
            "color_room_0": "Room 1",
            "color_room_1": "Room 2",
            "color_room_2": "Room 3",
            "color_room_3": "Room 4",
            "color_room_4": "Room 5",
            "color_room_5": "Room 6",
            "color_room_6": "Room 7",
            "color_room_7": "Room 8",
            "color_room_8": "Room 9",
            "color_room_9": "Room 10",
            "color_room_10": "Room 11",
            "color_room_11": "Room 12",
            "color_room_12": "Room 13",
            "color_room_13": "Room 14",
            "color_room_14": "Room 15",
            "color_room_15": "Room 16",
        }

        # Modify the "data_description" keys for rooms_colours_1 and rooms_colours_2
        for i in range(1, 3):
            room_key = f"rooms_colours_{i}"
            # For rooms_colours_1 use rooms 0-7, for rooms_colours_2 use 8-15
            start_index = 0 if i == 1 else 8
            end_index = 8 if i == 1 else 16

            # Ensure the room_key section exists
            room_section = step.setdefault(room_key, {})

            # Ensure data section exists with default values
            data_section = room_section.setdefault("data", {})
            for j in range(start_index, end_index):
                color_key = f"color_room_{j}"
                if color_key not in data_section and color_key in default_room_colors:
                    data_section[color_key] = default_room_colors[color_key]

            # Ensure data_description section exists
            data_description = room_section.setdefault("data_description", {})

            for j in range(start_index, end_index):
                color_key = f"color_room_{j}"
                if j < len(room_list):
                    room_id, room_info = room_list[j]
                    # Get the room name; if missing, fallback to a default name
                    room_name = room_info.get("name", f"Room {room_id}")
                    data_description[color_key] = (
                        f"### **RoomID {room_id} {room_name}**"
                    )
                else:
                    # Use default description or empty string if no room data
                    data_description[color_key] = default_room_descriptions.get(
                        color_key, ""
                    )

        # Modify the "data" keys for alpha_2 and alpha_3
        for i in range(2, 4):
            alpha_key = f"alpha_{i}"
            start_index = 0 if i == 2 else 8
            end_index = 8 if i == 2 else 16

            # Ensure the alpha_key section exists
            alpha_section = step.setdefault(alpha_key, {})
            alpha_data = alpha_section.setdefault("data", {})

            for j in range(start_index, end_index):
                alpha_room_key = f"alpha_room_{j}"
                if j < len(room_list):
                    room_id, room_info = room_list[j]
                    room_name = room_info.get("name", f"Room {room_id}")
                    alpha_data[alpha_room_key] = f"RoomID {room_id} {room_name}"
                else:
                    # Use default description or empty string if no room data
                    alpha_data[alpha_room_key] = default_room_descriptions.get(
                        f"color_room_{j}", ""
                    )

        return modified_data

    async def _write_json_file(self, file_path: str, data: dict) -> None:
        """
        Write JSON data to a file asynchronously.

        Args:
            file_path: The file path
            data: The data to write
        """
        try:
            await asyncio.to_thread(self._write_json, file_path, data)
            _LOGGER.debug("Successfully wrote translation file: %s", file_path)
        except Exception as e:
            _LOGGER.warning(
                "Error writing translation file %s: %s",
                file_path,
                str(e),
                exc_info=True,
            )

    @staticmethod
    def _write_json(file_path: str, data: dict) -> None:
        """
        Write JSON data to a file (to be called via asyncio.to_thread).

        Args:
            file_path: The file path
            data: The data to write
        """
        with open(file_path, "w") as file:
            json.dump(data, file, indent=2)

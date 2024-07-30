"""
This module contains type aliases for the project.
Version 2024.08.0b0
"""

import asyncio
from dataclasses import dataclass
import json
import logging
from typing import Any, Dict, Tuple, Union

from PIL import Image
import numpy as np

from .const import DEFAULT_ROOMS

_LOGGER = logging.getLogger(__name__)

Color = Union[Tuple[int, int, int], Tuple[int, int, int, int]]
Colors = Dict[str, Color]
CalibrationPoints = list[dict[str, Any]]
RobotPosition = dict[str, int | float]
ChargerPosition = dict[str, Any]
RoomsProperties = dict[str, dict[str, int | list[tuple[Any, Any]]]]
ImageSize = dict[str, int | list[int]]
JsonType = Any  # json.loads() return type is Any
PilPNG = Image.Image
NumpyArray = np.ndarray
Point = Tuple[int, int]


@dataclass
class TrimCropData:
    """Dataclass for trim and crop data."""

    trim_left: int
    trim_up: int
    trim_right: int
    trim_down: int

    def to_dict(self) -> dict:
        """Convert dataclass to dictionary."""
        return {
            "trim_left": self.trim_left,
            "trim_up": self.trim_up,
            "trim_right": self.trim_right,
            "trim_down": self.trim_down,
        }

    @staticmethod
    def from_dict(data: dict):
        """Create dataclass from dictionary."""
        return TrimCropData(
            trim_left=data["trim_left"],
            trim_up=data["trim_up"],
            trim_right=data["trim_right"],
            trim_down=data["trim_down"],
        )

    def to_list(self) -> list:
        """Convert dataclass to list."""
        return [self.trim_left, self.trim_up, self.trim_right, self.trim_down]

    @staticmethod
    def from_list(data: list):
        """Create dataclass from list."""
        return TrimCropData(
            trim_left=data[0],
            trim_up=data[1],
            trim_right=data[2],
            trim_down=data[3],
        )


class RoomStore:
    """Store the room data for the vacuum."""

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RoomStore, cls).__new__(cls)
            cls._instance.vacuums_data = {}
        return cls._instance

    async def async_set_rooms_data(self, vacuum_id: str, rooms_data: dict) -> None:
        """Set the room data for the vacuum."""
        async with self._lock:
            self.vacuums_data[vacuum_id] = rooms_data

    async def async_get_rooms_data(self, vacuum_id: str) -> dict:
        """Get the room data for a vacuum."""
        async with self._lock:
            data = self.vacuums_data.get(vacuum_id, {})
            if isinstance(data, str):
                json_data = json.loads(data)
                return json_data
            return data

    async def async_get_rooms_count(self, vacuum_id: str) -> int:
        """Count the number of rooms for a vacuum."""
        async with self._lock:
            count = len(self.vacuums_data.get(vacuum_id, {}))
            if count == 0:
                return DEFAULT_ROOMS
            return count


class UserLanguageStore:
    """Store the user language data."""

    _instance = None
    _lock = asyncio.Lock()
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UserLanguageStore, cls).__new__(cls)
            cls._instance.user_languages = {}
        return cls._instance

    async def set_user_language(self, user_id: str, language: str) -> None:
        """Set the user language."""
        async with self._lock:
            self.user_languages[user_id] = language

    async def get_user_language(self, user_id: str) -> str or None:
        """Get the user language."""
        async with self._lock:
            return self.user_languages.get(user_id, None)

    async def get_all_languages(self):
        """Get all the user languages."""
        async with self._lock:
            if not self.user_languages:
                return ["en"]
            return list(self.user_languages.values())

    @classmethod
    async def is_initialized(cls):
        """Return if the instance is initialized."""
        async with cls._lock:
            return bool(cls._initialized)

    @classmethod
    async def initialize_if_needed(cls, other_instance=None):
        """Initialize the instance if needed by copying from another instance if available."""
        async with cls._lock:
            if not cls._initialized and other_instance is not None:
                cls._instance.user_languages = other_instance.user_languages
                cls._initialized = True


class SnapshotStore:
    """Store the snapshot data."""

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SnapshotStore, cls).__new__(cls)
            cls._instance.snapshot_save_data = {}
            cls._instance.vacuum_json_data = {}
        return cls._instance

    async def async_set_snapshot_save_data(
        self, vacuum_id: str, snapshot_data: bool = False
    ) -> None:
        """Set the snapshot save data for the vacuum."""
        async with self._lock:
            self.snapshot_save_data[vacuum_id] = snapshot_data

    async def async_get_snapshot_save_data(self, vacuum_id: str) -> bool:
        """Get the snapshot save data for a vacuum."""
        async with self._lock:
            return self.snapshot_save_data.get(vacuum_id, False)

    async def async_get_vacuum_json(self, vacuum_id: str) -> Any:
        """Get the JSON data for a vacuum."""
        async with self._lock:
            return self.vacuum_json_data.get(vacuum_id, {})

    async def async_set_vacuum_json(self, vacuum_id: str, json_data: Any) -> None:
        """Set the JSON data for the vacuum."""
        async with self._lock:
            self.vacuum_json_data[vacuum_id] = json_data

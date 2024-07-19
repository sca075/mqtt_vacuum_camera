"""
This module contains type aliases for the project.
Version 2024.07.4
"""

from dataclasses import dataclass
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

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RoomStore, cls).__new__(cls)
            cls._instance.vacuums_data = {}
        return cls._instance

    def set_rooms_data(self, vacuum_id, rooms_data):
        """Set the room data for the vacuum."""
        self.vacuums_data[vacuum_id] = rooms_data

    def get_rooms_data(self, vacuum_id):
        """Get the room data for a vacuum."""
        return self.vacuums_data.get(vacuum_id, {})

    def get_rooms_count(self, vacuum_id):
        """Count the number of rooms for a vacuum."""
        count = len(self.vacuums_data.get(vacuum_id, {}))
        if count == 0:
            return DEFAULT_ROOMS
        return count

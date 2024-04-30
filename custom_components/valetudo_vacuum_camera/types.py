"""
This module contains type aliases for the project.
Version 1.5.9-rc2
"""

from typing import Any, Dict, Tuple, Union

from PIL import Image
import numpy as np

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

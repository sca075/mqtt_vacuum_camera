# version 1.1.8
from typing import Union, Tuple, Dict, Any

Color = Union[Tuple[int, int, int], Tuple[int, int, int, int]]
Colors = Dict[str, Color]
CalibrationPoints = list[dict[str, Any]]
RobotPosition = dict[str, int | float]
ChargerPosition = dict[str, Any]
RoomsProperties = dict[str, dict[str, int | list[tuple[Any, Any]]]]
ImageSize = dict[str, int | list[int]]

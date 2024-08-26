"""
Version: v2024.08.2
- This parser is the python version of @rand256 valetudo_mapper.
- This class is extracting the vacuum binary map_data.
- Additional functions are to get in our image_handler the images datas.
"""

from enum import Enum
import math
import struct
from typing import Any, Dict, List, Optional

from homeassistant.core import callback


# noinspection PyTypeChecker
class RRMapParser:
    """Parse the map data from the Rand256 vacuum."""

    def __init__(self):
        self.map_data = None

    class Tools:
        """Tools for the RRMapParser."""

        DIMENSION_PIXELS = 1024
        DIMENSION_MM = 50 * 1024

    class Types(Enum):
        """Types of blocks in the RRMapParser."""

        CHARGER_LOCATION = 1
        IMAGE = 2
        PATH = 3
        GOTO_PATH = 4
        GOTO_PREDICTED_PATH = 5
        CURRENTLY_CLEANED_ZONES = 6
        GOTO_TARGET = 7
        ROBOT_POSITION = 8
        FORBIDDEN_ZONES = 9
        VIRTUAL_WALLS = 10
        CURRENTLY_CLEANED_BLOCKS = 11
        FORBIDDEN_MOP_ZONES = 12
        DIGEST = 1024

    @staticmethod
    def parse_block(
        buf: bytes,
        offset: int,
        result: Optional[Dict[int, Any]] = None,
        pixels: bool = False,
    ) -> Dict[int, Any]:
        """Parse a block of data from the map data."""
        result = result or {}
        if len(buf) <= offset:
            return result

        type_ = struct.unpack("<H", buf[offset : offset + 2])[0]
        hlength = struct.unpack("<H", buf[offset + 2 : offset + 4])[0]
        length = struct.unpack("<I", buf[offset + 4 : offset + 8])[0]

        if type_ in (
            RRMapParser.Types.ROBOT_POSITION.value,
            RRMapParser.Types.CHARGER_LOCATION.value,
        ):
            result[type_] = {
                "position": [
                    int.from_bytes(buf[offset + 8 : offset + 10], byteorder="little"),
                    int.from_bytes(buf[offset + 12 : offset + 14], byteorder="little"),
                ],
                "angle": (
                    struct.unpack("<i", buf[offset + 16 : offset + 20])[0]
                    if length >= 12
                    else 0
                ),
            }
        elif type_ == RRMapParser.Types.IMAGE.value:
            RRMapParser._parse_image_block(buf, offset, length, hlength, result, pixels)
        elif type_ in (
            RRMapParser.Types.PATH.value,
            RRMapParser.Types.GOTO_PATH.value,
            RRMapParser.Types.GOTO_PREDICTED_PATH.value,
        ):
            result[type_] = RRMapParser._parse_path_block(buf, offset, length)
        elif type_ == RRMapParser.Types.GOTO_TARGET.value:
            result[type_] = {
                "position": [
                    struct.unpack("<H", buf[offset + 8 : offset + 10])[0],
                    struct.unpack("<H", buf[offset + 10 : offset + 12])[0],
                ]
            }
        elif type_ == RRMapParser.Types.CURRENTLY_CLEANED_ZONES.value:
            result[type_] = RRMapParser._parse_cleaned_zones(buf, offset, length)
        elif type_ in (
            RRMapParser.Types.FORBIDDEN_ZONES.value,
            RRMapParser.Types.FORBIDDEN_MOP_ZONES.value,
            RRMapParser.Types.VIRTUAL_WALLS.value,
        ):
            result[type_] = RRMapParser._parse_forbidden_zones(buf, offset, length)
        return RRMapParser.parse_block(buf, offset + length + hlength, result, pixels)

    @staticmethod
    def _parse_image_block(
        buf: bytes,
        offset: int,
        length: int,
        hlength: int,
        result: Dict[int, Any],
        pixels: bool,
    ) -> None:
        """Parse the image block of the map data."""
        g3offset = 4 if hlength > 24 else 0
        parameters = {
            "segments": {
                "count": (
                    struct.unpack("<i", buf[offset + 8 : offset + 12])[0]
                    if g3offset
                    else 0
                ),
                "id": [],
            },
            "position": {
                "top": struct.unpack(
                    "<i", buf[offset + 8 + g3offset : offset + 12 + g3offset]
                )[0],
                "left": struct.unpack(
                    "<i", buf[offset + 12 + g3offset : offset + 16 + g3offset]
                )[0],
            },
            "dimensions": {
                "height": struct.unpack(
                    "<i", buf[offset + 16 + g3offset : offset + 20 + g3offset]
                )[0],
                "width": struct.unpack(
                    "<i", buf[offset + 20 + g3offset : offset + 24 + g3offset]
                )[0],
            },
            "pixels": {"floor": [], "walls": [], "segments": {}},
        }
        parameters["position"]["top"] = (
            RRMapParser.Tools.DIMENSION_PIXELS
            - parameters["position"]["top"]
            - parameters["dimensions"]["height"]
        )
        if (
            parameters["dimensions"]["height"] > 0
            and parameters["dimensions"]["width"] > 0
        ):
            for i in range(length):
                segment_type = (
                    struct.unpack(
                        "<B",
                        buf[offset + 24 + g3offset + i : offset + 25 + g3offset + i],
                    )[0]
                    & 0x07
                )
                if segment_type == 0:
                    continue
                elif segment_type == 1 and pixels:
                    parameters["pixels"]["walls"].append(i)
                else:
                    s = (
                        struct.unpack(
                            "<B",
                            buf[
                                offset + 24 + g3offset + i : offset + 25 + g3offset + i
                            ],
                        )[0]
                        >> 3
                    )
                    if s == 0 and pixels:
                        parameters["pixels"]["floor"].append(i)
                    elif s != 0:
                        if s not in parameters["segments"]["id"]:
                            parameters["segments"]["id"].append(s)
                            parameters["segments"]["pixels_seg_" + str(s)] = []
                        if pixels:
                            parameters["segments"]["pixels_seg_" + str(s)].append(i)
        result[RRMapParser.Types.IMAGE.value] = parameters

    @staticmethod
    def _parse_path_block(buf: bytes, offset: int, length: int) -> Dict[str, Any]:
        """Parse a path block of the map data."""
        points = [
            [
                struct.unpack("<H", buf[offset + 20 + i : offset + 22 + i])[0],
                struct.unpack("<H", buf[offset + 22 + i : offset + 24 + i])[0],
            ]
            for i in range(0, length, 4)
        ]
        return {
            "current_angle": struct.unpack("<I", buf[offset + 16 : offset + 20])[0],
            "points": points,
        }

    @staticmethod
    def _parse_cleaned_zones(buf: bytes, offset: int, length: int) -> List[List[int]]:
        """Parse the cleaned zones block of the map data."""
        zone_count = struct.unpack("<I", buf[offset + 8 : offset + 12])[0]
        return (
            [
                [
                    struct.unpack("<H", buf[offset + 12 + i : offset + 14 + i])[0],
                    struct.unpack("<H", buf[offset + 14 + i : offset + 16 + i])[0],
                    struct.unpack("<H", buf[offset + 16 + i : offset + 18 + i])[0],
                    struct.unpack("<H", buf[offset + 18 + i : offset + 20 + i])[0],
                ]
                for i in range(0, length, 8)
            ]
            if zone_count > 0
            else []
        )

    @staticmethod
    def _parse_forbidden_zones(buf: bytes, offset: int, length: int) -> List[List[int]]:
        """Parse the forbidden zones block of the map data."""
        zone_count = struct.unpack("<I", buf[offset + 8 : offset + 12])[0]
        return (
            [
                [
                    struct.unpack("<H", buf[offset + 12 + i : offset + 14 + i])[0],
                    struct.unpack("<H", buf[offset + 14 + i : offset + 16 + i])[0],
                    struct.unpack("<H", buf[offset + 16 + i : offset + 18 + i])[0],
                    struct.unpack("<H", buf[offset + 18 + i : offset + 20 + i])[0],
                    struct.unpack("<H", buf[offset + 20 + i : offset + 22 + i])[0],
                    struct.unpack("<H", buf[offset + 22 + i : offset + 24 + i])[0],
                    struct.unpack("<H", buf[offset + 24 + i : offset + 26 + i])[0],
                    struct.unpack("<H", buf[offset + 26 + i : offset + 28 + i])[0],
                ]
                for i in range(0, length, 16)
            ]
            if zone_count > 0
            else []
        )

    @callback
    def PARSE(self, map_buf: bytes) -> Dict[str, Any]:
        """Parse the map data."""
        if map_buf[0:2] == b"rr":
            return {
                "header_length": struct.unpack("<H", map_buf[2:4])[0],
                "data_length": struct.unpack("<H", map_buf[4:6])[0],
                "version": {
                    "major": struct.unpack("<H", map_buf[8:10])[0],
                    "minor": struct.unpack("<H", map_buf[10:12])[0],
                },
                "map_index": struct.unpack("<H", map_buf[12:14])[0],
                "map_sequence": struct.unpack("<H", map_buf[16:18])[0],
            }
        return {}

    @callback
    def PARSEDATA(
        self, map_buf: bytes, pixels: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Parse the complete map data."""
        if not self.PARSE(map_buf).get("map_index"):
            return None

        parsed_map_data = {}
        blocks = self.parse_block(map_buf, 0x14, None, pixels)

        if RRMapParser.Types.IMAGE.value in blocks:
            parsed_map_data["image"] = blocks[RRMapParser.Types.IMAGE.value]
            for item in [
                {"type": RRMapParser.Types.PATH.value, "path": "path"},
                {
                    "type": RRMapParser.Types.GOTO_PREDICTED_PATH.value,
                    "path": "goto_predicted_path",
                },
            ]:
                if item["type"] in blocks:
                    parsed_map_data[item["path"]] = blocks[item["type"]]
                    parsed_map_data[item["path"]]["points"] = [
                        [point[0], RRMapParser.Tools.DIMENSION_MM - point[1]]
                        for point in parsed_map_data[item["path"]]["points"]
                    ]
                    if len(parsed_map_data[item["path"]]["points"]) >= 2:
                        parsed_map_data[item["path"]]["current_angle"] = math.degrees(
                            math.atan2(
                                parsed_map_data[item["path"]]["points"][-1][1]
                                - parsed_map_data[item["path"]]["points"][-2][1],
                                parsed_map_data[item["path"]]["points"][-1][0]
                                - parsed_map_data[item["path"]]["points"][-2][0],
                            )
                        )
        if RRMapParser.Types.CHARGER_LOCATION.value in blocks:
            charger = blocks[RRMapParser.Types.CHARGER_LOCATION.value]["position"]
            # Assume no transformation needed here
            parsed_map_data["charger"] = charger

        if RRMapParser.Types.ROBOT_POSITION.value in blocks:
            robot = blocks[RRMapParser.Types.ROBOT_POSITION.value]["position"]
            rob_angle = blocks[RRMapParser.Types.ROBOT_POSITION.value]["angle"]
            # Assume no transformation needed here
            parsed_map_data["robot"] = robot
            parsed_map_data["robot_angle"] = rob_angle

        if RRMapParser.Types.GOTO_TARGET.value in blocks:
            parsed_map_data["goto_target"] = blocks[
                RRMapParser.Types.GOTO_TARGET.value
            ]["position"]
            # Assume no transformation needed here

        if RRMapParser.Types.CURRENTLY_CLEANED_ZONES.value in blocks:
            parsed_map_data["currently_cleaned_zones"] = blocks[
                RRMapParser.Types.CURRENTLY_CLEANED_ZONES.value
            ]
            parsed_map_data["currently_cleaned_zones"] = [
                [
                    zone[0],
                    RRMapParser.Tools.DIMENSION_MM - zone[1],
                    zone[2],
                    RRMapParser.Tools.DIMENSION_MM - zone[3],
                ]
                for zone in parsed_map_data["currently_cleaned_zones"]
            ]

        if RRMapParser.Types.FORBIDDEN_ZONES.value in blocks:
            parsed_map_data["forbidden_zones"] = blocks[
                RRMapParser.Types.FORBIDDEN_ZONES.value
            ]
            parsed_map_data["forbidden_zones"] = [
                [
                    zone[0],
                    RRMapParser.Tools.DIMENSION_MM - zone[1],
                    zone[2],
                    RRMapParser.Tools.DIMENSION_MM - zone[3],
                    zone[4],
                    RRMapParser.Tools.DIMENSION_MM - zone[5],
                    zone[6],
                    RRMapParser.Tools.DIMENSION_MM - zone[7],
                ]
                for zone in parsed_map_data["forbidden_zones"]
            ]

        if RRMapParser.Types.VIRTUAL_WALLS.value in blocks:
            parsed_map_data["virtual_walls"] = blocks[
                RRMapParser.Types.VIRTUAL_WALLS.value
            ]
            parsed_map_data["virtual_walls"] = [
                [
                    wall[0],
                    RRMapParser.Tools.DIMENSION_MM - wall[1],
                    wall[2],
                    RRMapParser.Tools.DIMENSION_MM - wall[3],
                ]
                for wall in parsed_map_data["virtual_walls"]
            ]

        if RRMapParser.Types.CURRENTLY_CLEANED_BLOCKS.value in blocks:
            parsed_map_data["currently_cleaned_blocks"] = blocks[
                RRMapParser.Types.CURRENTLY_CLEANED_BLOCKS.value
            ]

        if RRMapParser.Types.FORBIDDEN_MOP_ZONES.value in blocks:
            parsed_map_data["forbidden_mop_zones"] = blocks[
                RRMapParser.Types.FORBIDDEN_MOP_ZONES.value
            ]
            parsed_map_data["forbidden_mop_zones"] = [
                [
                    zone[0],
                    RRMapParser.Tools.DIMENSION_MM - zone[1],
                    zone[2],
                    RRMapParser.Tools.DIMENSION_MM - zone[3],
                    zone[4],
                    RRMapParser.Tools.DIMENSION_MM - zone[5],
                    zone[6],
                    RRMapParser.Tools.DIMENSION_MM - zone[7],
                ]
                for zone in parsed_map_data["forbidden_mop_zones"]
            ]

        return parsed_map_data

    def parse_data(
        self, payload: Optional[bytes] = None, pixels: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get the map data from MQTT and return the json."""
        if payload:
            self.map_data = self.PARSE(payload)
            self.map_data.update(self.PARSEDATA(payload, pixels) or {})
        return self.map_data

    def get_image(self) -> Dict[str, Any]:
        """Get the image data from the map data."""
        return self.map_data.get("image", {})

    @staticmethod
    def get_int32(data: bytes, address: int) -> int:
        """Get a 32-bit integer from the data."""
        return struct.unpack_from("<i", data, address)[0]

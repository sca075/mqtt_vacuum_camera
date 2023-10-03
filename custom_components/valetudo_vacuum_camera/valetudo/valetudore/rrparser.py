import math

class Tools:
    DIMENSION_PIXELS = 1024
    DIMENSION_MM = 50 * 1024

    @staticmethod
    def flip_y_coordinate(coord):
        return Tools.DIMENSION_MM - coord


class RRMapParser:
    TYPES = {
        "CHARGER_LOCATION": 1,
        "IMAGE": 2,
        "PATH": 3,
        "GOTO_PATH": 4,
        "GOTO_PREDICTED_PATH": 5,
        "CURRENTLY_CLEANED_ZONES": 6,
        "GOTO_TARGET": 7,
        "ROBOT_POSITION": 8,
        "FORBIDDEN_ZONES": 9,
        "VIRTUAL_WALLS": 10,
        "CURRENTLY_CLEANED_BLOCKS": 11,
        "DIGEST": 1024,
    }

    @staticmethod
    def parse_block(buf, offset, result=None):
        result = result or {}
        if len(buf) <= offset:
            return result
        g3offset = 0
        type_ = buf.readUInt16LE(0x00 + offset)
        hlength = buf.readUInt16LE(0x02 + offset)
        length = buf.readUInt32LE(0x04 + offset)

        if type_ in (RRMapParser.TYPES["ROBOT_POSITION"], RRMapParser.TYPES["CHARGER_LOCATION"]):
            result[type_] = {
                "position": [
                    buf.readUInt16LE(0x08 + offset),
                    buf.readUInt16LE(0x0c + offset)
                ],
                "angle": buf.readInt32LE(0x10 + offset) if length >= 12 else None
            }
        elif type_ == RRMapParser.TYPES["IMAGE"]:
            if hlength > 24:
                g3offset = 4
            parameters = {
                "segments": {
                    "count": buf.readInt32LE(0x08 + offset) if g3offset else 0
                },
                "position": {
                    "top": buf.readInt32LE(0x08 + g3offset + offset),
                    "left": buf.readInt32LE(0x0c + g3offset + offset)
                },
                "dimensions": {
                    "height": buf.readInt32LE(0x10 + g3offset + offset),
                    "width": buf.readInt32LE(0x14 + g3offset + offset)
                },
                "pixels": {
                    "floor": [],
                    "obstacle_strong": [],
                    "segments": {}
                }
            }

            parameters["position"]["top"] = Tools.flip_y_coordinate(parameters["position"]["top"])

            if parameters["dimensions"]["height"] > 0 and parameters["dimensions"]["width"] > 0:
                for i in range(length):
                    val = buf.readUInt8(0x18 + g3offset + offset + i)
                    if (val & 0x07) == 0:
                        continue
                    coords = [
                        i % parameters["dimensions"]["width"],
                        parameters["dimensions"]["height"] - 1 - i // parameters["dimensions"]["width"]
                    ]
                    if (val & 0x07) == 1:
                        parameters["pixels"]["obstacle_strong"].append(coords)
                    else:
                        parameters["pixels"]["floor"].append(coords)
                        s = (val & 248) >> 3
                        if s != 0:
                            if s not in parameters["pixels"]["segments"]:
                                parameters["pixels"]["segments"][s] = []
                            parameters["pixels"]["segments"][s].append(coords)
            result[type_] = parameters
        elif type_ in (RRMapParser.TYPES["PATH"], RRMapParser.TYPES["GOTO_PATH"],
                       RRMapParser.TYPES["GOTO_PREDICTED_PATH"]):
            points = []
            for i in range(0, length, 4):
                points.append([
                    buf.readUInt16LE(0x14 + offset + i),
                    buf.readUInt16LE(0x14 + offset + i + 2)
                ])
                result[type_] = {
                    "current_angle": buf.readUInt32LE(0x10 + offset),
                    "points": points
                }
                for point in result[type_]["points"]:
                    point[1] = Tools.DIMENSION_MM - point[1]
        elif type_ == RRMapParser.TYPES["GOTO_TARGET"]:
            result[type_] = {
                "position": [
                    buf.readUInt16LE(0x08 + offset),
                    buf.readUInt16LE(0x0a + offset)
                ]
            }
            result[type_]["position"][1] = Tools.flip_y_coordinate(result[type_]["position"][1])
        elif type_ == RRMapParser.TYPES["CURRENTLY_CLEANED_ZONES"]:
            zone_count = buf.readUInt32LE(0x08 + offset)
            zones = []
            if zone_count > 0:
                for i in range(0, length, 8):
                    zones.append([
                        buf.readUInt16LE(0x0c + offset + i),
                        buf.readUInt16LE(0x0c + offset + i + 2),
                        buf.readUInt16LE(0x0c + offset + i + 4),
                        buf.readUInt16LE(0x0c + offset + i + 6)
                    ])
                    for zone in zones:
                        zone[1] = Tools.DIMENSION_MM - zone[1]
                        zone[3] = Tools.DIMENSION_MM - zone[3]
                result[type_] = zones
        elif type_ == RRMapParser.TYPES["FORBIDDEN_ZONES"]:
            forbidden_zone_count = buf.readUInt32LE(0x08 + offset)
            forbidden_zones = []
            if forbidden_zone_count > 0:
                for i in range(0, length, 16):
                    forbidden_zones.append([
                        buf.readUInt16LE(0x0c + offset + i),
                        buf.readUInt16LE(0x0c + offset + i + 2),
                        buf.readUInt16LE(0x0c + offset + i + 4),
                        buf.readUInt16LE(0x0c + offset + i + 6),
                        buf.readUInt16LE(0x0c + offset + i + 8),
                        buf.readUInt16LE(0x0c + offset + i + 10),
                        buf.readUInt16LE(0x0c + offset + i + 12),
                        buf.readUInt16LE(0x0c + offset + i + 14)
                    ])
                    for zone in forbidden_zones:
                        for i in range(8):
                            zone[i] = Tools.DIMENSION_MM - zone[i]
                result[type_] = forbidden_zones
        elif type_ == RRMapParser.TYPES["VIRTUAL_WALLS"]:
            wall_count = buf.readUInt32LE(0x08 + offset)
            walls = []
            if wall_count > 0:
                for i in range(0, length, 8):
                    walls.append([
                        buf.readUInt16LE(0x0c + offset + i),
                        buf.readUInt16LE(0x0c + offset + i + 2),
                        buf.readUInt16LE(0x0c + offset + i + 4),
                        buf.readUInt16LE(0x0c + offset + i + 6)
                    ])
                    for wall in walls:
                        wall[1] = Tools.DIMENSION_MM - wall[1]
                        wall[3] = Tools.DIMENSION_MM - wall[3]
                result[type_] = walls
        elif type_ == RRMapParser.TYPES["CURRENTLY_CLEANED_BLOCKS"]:
            block_count = buf.readUInt32LE(0x08 + offset)
            blocks = []
            if block_count > 0:
                for i in range(length):
                    blocks.append(buf.readUInt8(0x0c + offset + i))
                result[type_] = blocks
        else:
            pass  # Unknown Data Block

        return RRMapParser.parse_block(buf, offset + length + hlength, result)

    @staticmethod
    def parse(map_buf):
        if map_buf[0x00] == 0x72 and map_buf[0x01] == 0x72:  # rr
            print("ok")
            blocks = RRMapParser.parse_block(map_buf, 0x14)
            parsed_map_data = {
                "header_length": map_buf.readUInt16LE(0x02),
                "data_length": map_buf.readUInt16LE(0x04),
                "version": {
                    "major": map_buf.readUInt16LE(0x08),
                    "minor": map_buf.readUInt16LE(0x0A)
                },
                "map_index": map_buf.readUInt16LE(0x0C),
                "map_sequence": map_buf.readUInt16LE(0x10)
            }

            if blocks[RRMapParser.TYPES["IMAGE"]]:  # We need the image to flip everything else correctly
                parsed_map_data["image"] = blocks[RRMapParser.TYPES["IMAGE"]]

                for item in [
                    {
                        "type": RRMapParser.TYPES["PATH"],
                        "path": "path"
                    },
                    {
                        "type": RRMapParser.TYPES["GOTO_PATH"],
                        "path": "goto_path"
                    },
                    {
                        "type": RRMapParser.TYPES["GOTO_PREDICTED_PATH"],
                        "path": "goto_predicted_path"
                    },
                ]:
                    if blocks[item["type"]]:
                        parsed_map_data[item["path"]] = blocks[item["type"]]
                        parsed_map_data[item["path"]]["points"] = [
                            [point[0], Tools.DIMENSION_MM - point[1]] for point in
                            parsed_map_data[item["path"]]["points"]
                        ]
                        if len(parsed_map_data[item["path"]]["points"]) >= 2:
                            parsed_map_data[item["path"]]["current_angle"] = \
                                math.atan2(
                                    parsed_map_data[item["path"]]["points"][-1][1] -
                                    parsed_map_data[item["path"]]["points"][-2][1],

                                    parsed_map_data[item["path"]]["points"][-1][0] -
                                    parsed_map_data[item["path"]]["points"][-2][0]
                                ) * 180 / math.pi

                if blocks[RRMapParser.TYPES["CHARGER_LOCATION"]]:
                    parsed_map_data["charger"] = blocks[RRMapParser.TYPES["CHARGER_LOCATION"]]["position"]
                    parsed_map_data["charger"][1] = Tools.DIMENSION_MM - parsed_map_data["charger"][1]

                if blocks[RRMapParser.TYPES["ROBOT_POSITION"]]:
                    parsed_map_data["robot"] = blocks[RRMapParser.TYPES["ROBOT_POSITION"]]["position"]
                    parsed_map_data["robot"][1] = Tools.DIMENSION_MM - parsed_map_data["robot"][1]

                parsed_map_data["robot_angle"] = blocks[RRMapParser.TYPES["ROBOT_POSITION"]]["angle"] if \
                    blocks[RRMapParser.TYPES["ROBOT_POSITION"]] and \
                    blocks[RRMapParser.TYPES["ROBOT_POSITION"]]["angle"] is not None else \
                    (parsed_map_data["path"]["current_angle"] + 90) if "path" in parsed_map_data else 0

                if blocks[RRMapParser.TYPES["GOTO_TARGET"]]:
                    parsed_map_data["goto_target"] = blocks[RRMapParser.TYPES["GOTO_TARGET"]]["position"]
                    parsed_map_data["goto_target"][1] = Tools.DIMENSION_MM - parsed_map_data["goto_target"][1]

                if blocks[RRMapParser.TYPES["CURRENTLY_CLEANED_ZONES"]]:
                    parsed_map_data["currently_cleaned_zones"] = blocks[RRMapParser.TYPES["CURRENTLY_CLEANED_ZONES"]]
                    parsed_map_data["currently_cleaned_zones"] = [
                        [
                            zone[0],
                            Tools.DIMENSION_MM - zone[1],
                            zone[2],
                            Tools.DIMENSION_MM - zone[3]
                        ] for zone in parsed_map_data["currently_cleaned_zones"]
                    ]

                if blocks[RRMapParser.TYPES["FORBIDDEN_ZONES"]]:
                    parsed_map_data["forbidden_zones"] = blocks[RRMapParser.TYPES["FORBIDDEN_ZONES"]]
                    parsed_map_data["forbidden_zones"] = [
                        [
                            zone[0],
                            Tools.DIMENSION_MM - zone[1],
                            zone[2],
                            Tools.DIMENSION_MM - zone[3],
                            zone[4],
                            Tools.DIMENSION_MM - zone[5],
                            zone[6],
                            Tools.DIMENSION_MM - zone[7]
                        ] for zone in parsed_map_data["forbidden_zones"]
                    ]

                if blocks[RRMapParser.TYPES["VIRTUAL_WALLS"]]:
                    parsed_map_data["virtual_walls"] = blocks[RRMapParser.TYPES["VIRTUAL_WALLS"]]
                    parsed_map_data["virtual_walls"] = [
                        [
                            wall[0],
                            Tools.DIMENSION_MM - wall[1],
                            wall[2],
                            Tools.DIMENSION_MM - wall[3]
                        ]
                        for wall in blocks[RRMapParser.TYPES["VIRTUAL_WALLS"]]
                    ]

                if blocks[RRMapParser.TYPES["CURRENTLY_CLEANED_BLOCKS"]]:
                    parsed_map_data["currently_cleaned_blocks"] = blocks[RRMapParser.TYPES["CURRENTLY_CLEANED_BLOCKS"]]

                return parsed_map_data
            else:
                print("something went wrong")
                return None
        else:
            print("invalid data")
            return None

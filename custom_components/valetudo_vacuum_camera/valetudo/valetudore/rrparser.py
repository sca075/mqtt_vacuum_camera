import struct
import math

class RRMapParser:
    TOOLS = {
        "DIMENSION_PIXELS": 1024,
        "DIMENSION_MM": 50 * 1024
    }

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
        "FORBIDDEN_MOP_ZONES": 12,
        "DIGEST": 1024
    }

    @staticmethod
    def parseBlock(buf, offset, result=None, pixels=False):
        result = result or {}
        if len(buf) <= offset:
            return result
        g3offset = 0
        type_ = struct.unpack("<H", buf[0x00 + offset:0x02 + offset])[0]
        hlength = struct.unpack("<H", buf[0x02 + offset:0x04 + offset])[0]
        length = struct.unpack("<I", buf[0x04 + offset:0x08 + offset])[0]
        if type_ == RRMapParser.TYPES["ROBOT_POSITION"] or type_ == RRMapParser.TYPES["CHARGER_LOCATION"]:
            result[type_] = {
                "position": [
                    struct.unpack("<H", buf[0x08 + offset:0x0A + offset])[0],
                    struct.unpack("<H", buf[0x0A + offset:0x0C + offset])[0]
                ],
                "angle": struct.unpack("<i", buf[0x10 + offset:0x14 + offset])[0] if length >= 12 else 0
            }
        elif type_ == RRMapParser.TYPES["IMAGE"]:
            if hlength > 24:
                g3offset = 4
            parameters = {
                "segments": {
                    "count": struct.unpack("<i", buf[0x08 + offset:0x0C + offset])[0] if g3offset else 0,
                    "id": [],
                },
                "position": {
                    "top": struct.unpack("<i", buf[0x08 + g3offset + offset:0x0C + g3offset + offset])[0],
                    "left": struct.unpack("<i", buf[0x0C + g3offset + offset:0x10 + g3offset + offset])[0]
                },
                "dimensions": {
                    "height": struct.unpack("<i", buf[0x10 + g3offset + offset:0x14 + g3offset + offset])[0],
                    "width": struct.unpack("<i", buf[0x14 + g3offset + offset:0x18 + g3offset + offset])[0]
                },
                "pixels": {
                    "floor": [],
                    "obstacle": [],
                    "segments": []
                }
            }
            parameters["position"]["top"] = RRMapParser.TOOLS["DIMENSION_PIXELS"] - parameters["position"]["top"] - parameters["dimensions"]["height"]
            if parameters["dimensions"]["height"] > 0 and parameters["dimensions"]["width"] > 0:
                for i in range(length):
                    segment_type = struct.unpack("<B", buf[0x18 + g3offset + offset + i:0x19 + g3offset + offset + i])[0] & 0x07
                    if segment_type == 0:
                        continue
                    elif segment_type == 1:
                        if pixels:
                            parameters["pixels"]["obstacle"].append(i)
                    else:
                        if pixels:
                            parameters["pixels"]["floor"].append(i)
                        s = (struct.unpack("<B", buf[0x18 + g3offset + offset + i:0x19 + g3offset + offset + i])[0] & 248) >> 3
                        if s != 0:
                            if s not in parameters["segments"]["id"]:
                                parameters["segments"]["id"].append(s)
                            if pixels:
                                parameters["pixels"]["segments"].append(i | (s << 21))
            result[type_] = parameters
        elif type_ in [RRMapParser.TYPES["PATH"], RRMapParser.TYPES["GOTO_PATH"], RRMapParser.TYPES["GOTO_PREDICTED_PATH"]]:
            points = []
            for i in range(0, length, 4):
                points.append([
                    struct.unpack("<H", buf[0x14 + offset + i:0x16 + offset + i])[0],
                    struct.unpack("<H", buf[0x16 + offset + i:0x18 + offset + i])[0]
                ])
            result[type_] = {
                "current_angle": struct.unpack("<I", buf[0x10 + offset:0x14 + offset])[0],
                "points": points
            }
        elif type_ == RRMapParser.TYPES["GOTO_TARGET"]:
            result[type_] = {
                "position": [
                    struct.unpack("<H", buf[0x08 + offset:0x0A + offset])[0],
                    struct.unpack("<H", buf[0x0A + offset:0x0C + offset])[0]
                ]
            }
        elif type_ == RRMapParser.TYPES["CURRENTLY_CLEANED_ZONES"]:
            zoneCount = struct.unpack("<I", buf[0x08 + offset:0x0C + offset])[0]
            zones = []
            if zoneCount > 0:
                for i in range(0, length, 8):
                    zones.append([
                        struct.unpack("<H", buf[0x0C + offset + i:0x0E + offset + i])[0],
                        struct.unpack("<H", buf[0x0E + offset + i:0x10 + offset + i])[0],
                        struct.unpack("<H", buf[0x10 + offset + i:0x12 + offset + i])[0],
                        struct.unpack("<H", buf[0x12 + offset + i:0x14 + offset + i])[0]
                    ])
                result[type_] = zones
        elif type_ in [RRMapParser.TYPES["FORBIDDEN_ZONES"], RRMapParser.TYPES["FORBIDDEN_MOP_ZONES"]]:
            forbiddenZoneCount = struct.unpack("<I", buf[0x08 + offset:0x0C + offset])[0]
            forbiddenZones = []
            if forbiddenZoneCount > 0:
                for i in range(0, length, 16):
                    forbiddenZones.append([
                        struct.unpack("<H", buf[0x0C + offset + i:0x0E + offset + i])[0],
                        struct.unpack("<H", buf[0x0E + offset + i:0x10 + offset + i])[0],
                        struct.unpack("<H", buf[0x10 + offset + i:0x12 + offset + i])[0],
                        struct.unpack("<H", buf[0x12 + offset + i:0x14 + offset + i])[0],
                        struct.unpack("<H", buf[0x14 + offset + i:0x16 + offset + i])[0],
                        struct.unpack("<H", buf[0x16 + offset + i:0x18 + offset + i])[0],
                        struct.unpack("<H", buf[0x18 + offset + i:0x1A + offset + i])[0],
                        struct.unpack("<H", buf[0x1A + offset + i:0x1C + offset + i])[0]
                    ])
                result[type_] = forbiddenZones
        return RRMapParser.parseBlock(buf, offset + length + hlength, result)

    @staticmethod
    def PARSE(mapBuf):
        if mapBuf[0x00] == 0x72 and mapBuf[0x01] == 0x72:
            parsedMapData = {
                "header_length": struct.unpack("<H", mapBuf[0x02:0x04])[0],
                "data_length": struct.unpack("<H", mapBuf[0x04:0x06])[0],
                "version": {
                    "major": struct.unpack("<H", mapBuf[0x08:0x0A])[0],
                    "minor": struct.unpack("<H", mapBuf[0x0A:0x0C])[0]
                },
                "map_index": struct.unpack("<H", mapBuf[0x0C:0x0E])[0],
                "map_sequence": struct.unpack("<H", mapBuf[0x10:0x12])[0]
            }
            return parsedMapData
        else:
            return {}

    @staticmethod
    def PARSEDATA(mapBuf, pixels=False):
        if not RRMapParser.PARSE(mapBuf)["map_index"]:
            return None
        blocks = RRMapParser.parseBlock(mapBuf, 0x14, None, pixels)
        parsedMapData = {}
        if blocks[RRMapParser.TYPES["IMAGE"]]:
            parsedMapData["image"] = blocks[RRMapParser.TYPES["IMAGE"]]
            for item in [
                {
                    "type": RRMapParser.TYPES["PATH"],
                    "path": "path"
                },
                {
                    "type": RRMapParser.TYPES["GOTO_PREDICTED_PATH"],
                    "path": "goto_predicted_path"
                }
            ]:
                if item["type"] in blocks:
                    parsedMapData[item["path"]] = blocks[item["type"]]
                    parsedMapData[item["path"]]["points"] = [
                        [point[0], RRMapParser.TOOLS["DIMENSION_MM"] - point[1]] for point in parsedMapData[item["path"]]["points"]
                    ]
                    if len(parsedMapData[item["path"]]["points"]) >= 2:
                        parsedMapData[item["path"]]["current_angle"] = math.degrees(
                            math.atan2(
                                parsedMapData[item["path"]]["points"][-1][1] - parsedMapData[item["path"]]["points"][-2][1],
                                parsedMapData[item["path"]]["points"][-1][0] - parsedMapData[item["path"]]["points"][-2][0]
                            )
                        )
                if RRMapParser.TYPES["CHARGER_LOCATION"] in blocks:
                    parsedMapData["charger"] = blocks[RRMapParser.TYPES["CHARGER_LOCATION"]]["position"]
                    parsedMapData["charger"][1] = RRMapParser.TOOLS["DIMENSION_MM"] - parsedMapData["charger"][1]
                if RRMapParser.TYPES["ROBOT_POSITION"] in blocks:
                    parsedMapData["robot"] = blocks[RRMapParser.TYPES["ROBOT_POSITION"]]["position"]
                    parsedMapData["robot"][1] = RRMapParser.TOOLS["DIMENSION_MM"] - parsedMapData["robot"][1]
                    parsedMapData["robot_angle"] = parsedMapData["robot"][0] if "robot" in parsedMapData else \
                        parsedMapData["path"]["current_angle"] if "path" in parsedMapData else 0
                if RRMapParser.TYPES["GOTO_TARGET"] in blocks:
                    parsedMapData["goto_target"] = blocks[RRMapParser.TYPES["GOTO_TARGET"]]["position"]
                    parsedMapData["goto_target"][1] = RRMapParser.TOOLS["DIMENSION_MM"] - parsedMapData["goto_target"][1]
                if RRMapParser.TYPES["CURRENTLY_CLEANED_ZONES"] in blocks:
                    parsedMapData["currently_cleaned_zones"] = blocks[RRMapParser.TYPES["CURRENTLY_CLEANED_ZONES"]]
                    parsedMapData["currently_cleaned_zones"] = [
                        [zone[0], RRMapParser.TOOLS["DIMENSION_MM"] - zone[1], zone[2], RRMapParser.TOOLS["DIMENSION_MM"] - zone[3]]
                        for zone in parsedMapData["currently_cleaned_zones"]
                    ]
                if RRMapParser.TYPES["FORBIDDEN_ZONES"] in blocks:
                    parsedMapData["forbidden_zones"] = blocks[RRMapParser.TYPES["FORBIDDEN_ZONES"]]
                    parsedMapData["forbidden_zones"] = [
                        [zone[0], RRMapParser.TOOLS["DIMENSION_MM"] - zone[1], zone[2], RRMapParser.TOOLS["DIMENSION_MM"] - zone[3],
                         zone[4], RRMapParser.TOOLS["DIMENSION_MM"] - zone[5], zone[6], RRMapParser.TOOLS["DIMENSION_MM"] - zone[7]]
                        for zone in parsedMapData["forbidden_zones"]
                    ]
                if RRMapParser.TYPES["VIRTUAL_WALLS"] in blocks:
                    parsedMapData["virtual_walls"] = blocks[RRMapParser.TYPES["VIRTUAL_WALLS"]]
                    parsedMapData["virtual_walls"] = [
                        [wall[0], RRMapParser.TOOLS["DIMENSION_MM"] - wall[1], wall[2], RRMapParser.TOOLS["DIMENSION_MM"] - wall[3]]
                        for wall in parsedMapData["virtual_walls"]
                    ]
                if RRMapParser.TYPES["CURRENTLY_CLEANED_BLOCKS"] in blocks:
                    parsedMapData["currently_cleaned_blocks"] = blocks[RRMapParser.TYPES["CURRENTLY_CLEANED_BLOCKS"]]
                if RRMapParser.TYPES["FORBIDDEN_MOP_ZONES"] in blocks:
                    parsedMapData["forbidden_mop_zones"] = blocks[RRMapParser.TYPES["FORBIDDEN_MOP_ZONES"]]
                    parsedMapData["forbidden_mop_zones"] = [
                        [zone[0], RRMapParser.TOOLS["DIMENSION_MM"] - zone[1], zone[2], RRMapParser.TOOLS["DIMENSION_MM"] - zone[3],
                         zone[4], RRMapParser.TOOLS["DIMENSION_MM"] - zone[5], zone[6], RRMapParser.TOOLS["DIMENSION_MM"] - zone[7]]
                        for zone in parsedMapData["forbidden_mop_zones"]
                    ]
        return parsedMapData


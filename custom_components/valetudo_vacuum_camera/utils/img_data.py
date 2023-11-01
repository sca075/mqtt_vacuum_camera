"""
Collections of Json and List routines
ImageData is part of the Image_Handler
used functions to search data in the json
provided for the creation of the new camera frame
Last changes on Version: 1.4.8
"""

import logging

import numpy as np

_LOGGER = logging.getLogger(__name__)


class ImageData:

    @staticmethod
    def sublist(lst, n):
        """ Sub lists of specific n number of elements """
        return [lst[i: i + n] for i in range(0, len(lst), n)]

    @staticmethod
    def sublist_join(lst, n):
        """ Join the lists in a unique list of n elements """
        arr = np.array(lst)
        num_windows = len(lst) - n + 1
        result = [arr[i: i + n].tolist() for i in range(num_windows)]
        return result

    """ 
    The below functions are basically the same ech one
    of them is allowing filtering and putting together in a
    list the specific Layers, Paths, Zones and Pints in the 
    Vacuums Json in parallel.
    """

    @staticmethod
    def find_layers(json_obj, layer_dict=None):
        if layer_dict is None:
            layer_dict = {}
        if isinstance(json_obj, dict):
            if "__class" in json_obj and json_obj["__class"] == "MapLayer":
                layer_type = json_obj.get("type")
                if layer_type:
                    if layer_type not in layer_dict:
                        layer_dict[layer_type] = []
                    layer_dict[layer_type].append(json_obj.get("compressedPixels", []))
            for value in json_obj.items():
                ImageData.find_layers(value, layer_dict)
        elif isinstance(json_obj, list):
            for item in json_obj:
                ImageData.find_layers(item, layer_dict)
        return layer_dict

    @staticmethod
    def find_points_entities(json_obj, entity_dict=None):
        if entity_dict is None:
            entity_dict = {}
        if isinstance(json_obj, dict):
            if json_obj.get("__class") == "PointMapEntity":
                entity_type = json_obj.get("type")
                if entity_type:
                    entity_dict.setdefault(entity_type, []).append(json_obj)
            for value in json_obj.values():
                ImageData.find_points_entities(value, entity_dict)
        elif isinstance(json_obj, list):
            for item in json_obj:
                ImageData.find_points_entities(item, entity_dict)
        return entity_dict

    @staticmethod
    def find_paths_entities(json_obj, entity_dict=None):
        if entity_dict is None:
            entity_dict = {}
        if isinstance(json_obj, dict):
            if json_obj.get("__class") == "PathMapEntity":
                entity_type = json_obj.get("type")
                if entity_type:
                    entity_dict.setdefault(entity_type, []).append(json_obj)
            for value in json_obj.values():
                ImageData.find_paths_entities(value, entity_dict)
        elif isinstance(json_obj, list):
            for item in json_obj:
                ImageData.find_paths_entities(item, entity_dict)
        return entity_dict

    @staticmethod
    def find_zone_entities(json_obj, entity_dict=None):
        if entity_dict is None:
            entity_dict = {}
        if isinstance(json_obj, dict):
            if json_obj.get("__class") == "PolygonMapEntity":
                entity_type = json_obj.get("type")
                if entity_type:
                    entity_dict.setdefault(entity_type, []).append(json_obj)
            for value in json_obj.values():
                ImageData.find_zone_entities(value, entity_dict)
        elif isinstance(json_obj, list):
            for item in json_obj:
                ImageData.find_zone_entities(item, entity_dict)
        return entity_dict

    @staticmethod
    def find_virtual_walls(json_obj):
        virtual_walls = []

        def find_virtual_walls_recursive(obj):
            if isinstance(obj, dict):
                if obj.get("__class") == "LineMapEntity":
                    entity_type = obj.get("type")
                    if entity_type == "virtual_wall":
                        virtual_walls.append(obj["points"])
                for value in obj.values():
                    find_virtual_walls_recursive(value)
            elif isinstance(obj, list):
                for item in obj:
                    find_virtual_walls_recursive(item)

        find_virtual_walls_recursive(json_obj)
        return virtual_walls

    """ 
    Added below in order to support Valetudo Re.
    This functions read directly the data from the json created
    from the parser for Valetudo Re. They allow to use the 
    fuctions to draw the image without changes.
    """

    @staticmethod
    def from_rrm_to_compressed_pixels(pixel_data, image_width=0, image_height=0, image_top=0, image_left=0):
        compressed_pixels = []

        tot_pixels = 0
        current_x, current_y, count = None, None, 0
        for index in pixel_data:
            x = (index % image_width) + image_left
            y = ((image_height-1) - (index // image_width)) + image_top

            if current_x == x and current_y == y:
                count += 1
            else:
                if current_x is not None:
                    compressed_pixels.append([current_x, current_y, count])
                current_x, current_y, count = x, y, 1
            tot_pixels += 1
        if current_x is not None:
            compressed_pixels.append([current_x, current_y, count])
        return compressed_pixels

    @staticmethod
    def calculate_max_x_y(coord_array):
        max_x = -float('inf')
        max_y = -float('inf')

        for x, y, count in coord_array:
            max_x = max(max_x, x)
            max_y = max(max_y, y)

        max_x = max_x * 6
        max_y = max_y * 6
        return max_x, max_y

    @staticmethod
    def rrm_coordinates_to_valetudo(points):
        transformed_points = []
        dimension_mm = 50 * 1024
        for i, p in enumerate(points):
            if i % 2 == 0:
                transformed_points.append(round(p / 10))
            else:
                transformed_points.append(round((dimension_mm-p) / 10))
        return transformed_points

    @staticmethod
    def rrm_valetudo_path_array(points):
        transformed_points = []
        for point in points:
            transformed_x = round(point[0] / 10)
            transformed_y = round(point[1] / 10)
            transformed_points.extend([[transformed_x, transformed_y]])
        return transformed_points

    @staticmethod
    def get_rrm_image(json_data):
        return json_data.get("image", {})

    @staticmethod
    def get_rrm_path(json_data):
        return json_data.get("path", {})

    @staticmethod
    def get_rrm_goto_predicted_path(json_data):
        try:
            predicted_path = json_data.get("goto_predicted_path", {})
            points = predicted_path['points']
        except KeyError:
            return None
        else:
            predicted_path = ImageData.sublist_join(
                ImageData.rrm_valetudo_path_array(points), 2)
            _LOGGER.debug(predicted_path)
        return predicted_path

    @staticmethod
    def get_rrm_charger_position(json_data):
        return json_data.get("charger", {})

    @staticmethod
    def get_rrm_robot_position(json_data):
        return json_data.get("robot", {})

    @staticmethod
    def get_rrm_robot_angle(json_data):
        # todo robot angle require debug.
        angle = (json_data.get("robot_angle", 0) + 90) % 360
        return angle, json_data.get("robot_angle", 0)

    @staticmethod
    def get_rrm_goto_target(json_data):
        try:
            path_data = json_data.get("goto_target", {})
        except KeyError:
            return None
        else:
            if path_data is not []:
                path_data = ImageData.rrm_coordinates_to_valetudo(path_data)
                return path_data
            else:
                return None

    @staticmethod
    def get_rrm_currently_cleaned_zones(json_data):
        re_zones = json_data.get("currently_cleaned_zones", [])
        formatted_zones = ImageData.rrm_valetudo_format_zone(re_zones)
        return formatted_zones

    @staticmethod
    def get_rrm_forbidden_zones(json_data):
        re_zones = json_data.get("forbidden_zones", [])
        formatted_zones = ImageData.rrm_valetudo_format_zone(re_zones)
        return formatted_zones

    @staticmethod
    def rrm_valetudo_format_zone(coordinates):
        formatted_zones = []
        for zone_data in coordinates:
            if len(zone_data) == 4:  # This is a zone_clean (4 coordinates)
                formatted_zone = {
                    "__class": "PolygonMapEntity",
                    "metaData": {},
                    "points": [
                        zone_data[0] // 10,
                        zone_data[1] // 10,
                        zone_data[2] // 10,
                        zone_data[1] // 10,
                        zone_data[2] // 10,
                        zone_data[3] // 10,
                        zone_data[0] // 10,
                        zone_data[3] // 10,
                        ],
                    "type": "zone_clean",
                }
                formatted_zones.append(formatted_zone)
            elif len(zone_data) == 8:  # This is a no_go_area (8 coordinates)
                formatted_zone = {
                    "__class": "PolygonMapEntity",
                    "metaData": {},
                    "points": [
                        zone_data[0] // 10,
                        zone_data[1] // 10,
                        zone_data[2] // 10,
                        zone_data[3] // 10,
                        zone_data[4] // 10,
                        zone_data[5] // 10,
                        zone_data[6] // 10,
                        zone_data[7] // 10,
                        ],
                    "type": "no_go_area",
                }
                formatted_zones.append(formatted_zone)

        return formatted_zones

    @staticmethod
    def rrm_valetudo_lines(coordinates):
        formatted_lines = []
        for lines in coordinates:
            line = [lines[0] // 10,
                    lines[1] // 10,
                    lines[2] // 10,
                    lines[3] // 10
                    ]
            formatted_lines.append(line)
        return formatted_lines

    @staticmethod
    def get_rrm_virtual_walls(json_data):
        try:
            tmp_data = json_data.get("virtual_walls", [])
        except KeyError:
            return None
        virtual_walls = ImageData.rrm_valetudo_lines(tmp_data)
        return virtual_walls

    @staticmethod
    def get_rrm_currently_cleaned_blocks(json_data):
        return json_data.get("currently_cleaned_blocks", [])

    @staticmethod
    def get_rrm_forbidden_mop_zones(json_data):
        return json_data.get("forbidden_mop_zones", [])

    @staticmethod
    def get_rrm_image_size(json_data):
        image = ImageData.get_rrm_image(json_data)
        dimensions = image.get("dimensions", {})
        return dimensions.get("width", 0), dimensions.get("height", 0)

    @staticmethod
    def get_rrm_image_position(json_data):
        image = ImageData.get_rrm_image(json_data)
        position = image.get("position", {})
        return position.get("top", 0), position.get("left", 0)

    @staticmethod
    def get_rrm_floor(json_data):
        img = ImageData.get_rrm_image(json_data)
        return img.get("pixels", {}).get("floor", [])

    @staticmethod
    def get_rrm_walls(json_data):
        img = ImageData.get_rrm_image(json_data)
        return img.get("pixels", {}).get("walls", [])

    @staticmethod
    def get_rrm_segments(json_data, size_x, size_y, pos_top, pos_left):
        img = ImageData.get_rrm_image(json_data)
        seg_data = img.get("segments", [])
        seg_ids = seg_data.get("id")
        print(seg_ids)
        segments = []
        count_seg = 0
        for id_seg in seg_ids:
            tmp_data = seg_data.get("pixels_seg_"+str(id_seg))
            segments.append(
                ImageData.from_rrm_to_compressed_pixels(tmp_data,
                                                        image_width=size_x,
                                                        image_height=size_y,
                                                        image_top=pos_top,
                                                        image_left=pos_left))
            count_seg += 1
        if count_seg > 0:
            return segments
        else:
            return []

    @staticmethod
    def convert_negative_angle(angle):
        angle = angle % 360  # Ensure angle is within 0-359
        if angle < 0:
            angle += 360  # Convert negative angle to positive
        angle = angle + 180  # add offset
        return angle

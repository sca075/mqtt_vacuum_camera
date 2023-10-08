"""
Collections of Json and List routines
ImageData is part of the Image_Handler
used functions to search data in the json
provided for the creation of the new camera frame
Last changes on Version: 1.4.5
"""

import logging

import numpy as np

_LOGGER = logging.getLogger(__name__)


class ImageData:

    @staticmethod
    def sublist(lst, n):
        """ Sub lists of specific n number of elements """
        return [lst[i : i + n] for i in range(0, len(lst), n)]

    @staticmethod
    def sublist_join(lst, n):
        """ Join the lists in a unique list of n elements """
        arr = np.array(lst)
        num_windows = len(lst) - n + 1
        result = [arr[i : i + n].tolist() for i in range(num_windows)]
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
    def from_rrm_to_compressed_pixels(pixel_data, image_width, image_height):
        compressed_pixels = []

        current_x, current_y, count = None, None, 0

        for index in pixel_data:
            x = index % image_width
            y = index // image_width
            if current_x == x and current_y == y:
                count += 1
            else:
                if current_x is not None:
                    compressed_pixels.append([current_x, current_y, count])
                current_x, current_y, count = x, y, 1

        if current_x is not None:
            compressed_pixels.append([current_x, current_y, count])

        return compressed_pixels

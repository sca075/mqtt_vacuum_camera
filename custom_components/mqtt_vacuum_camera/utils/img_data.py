"""
Collections of Json and List routines
ImageData is part of the Image_Handler
used functions to search data in the json
provided for the creation of the new camera frame
Version: v2024.08.2
"""

from __future__ import annotations

import numpy as np

from custom_components.mqtt_vacuum_camera.types import (
    Colors,
    ImageSize,
    JsonType,
    NumpyArray,
)


class ImageData:
    """Class to handle the image data."""

    @staticmethod
    async def async_extract_color_coordinates(
        source_array: NumpyArray, search_for_colours_list: Colors
    ) -> list:
        """Search for specific colors in an image array and return their coordinates."""
        # Initialize an empty list to store color and coordinates tuples
        color_coordinates_list = []

        # Iterate over the search_for_colours_list
        for color_to_search in search_for_colours_list:
            # Initialize an empty list to store coordinates for the current color
            color_coordinates = []

            # Iterate over the image array
            for y in range(source_array.shape[0]):
                for x in range(source_array.shape[1]):
                    # Extract the pixel color at the current coordinates
                    pixel_color = source_array[y, x]

                    # Check if the current pixel color matches the color_to_search
                    if np.all(pixel_color == color_to_search):
                        # Record the coordinates for the current color
                        color_coordinates.append((x, y))

            # Append the color and its coordinates to the final list
            color_coordinates_list.append((color_to_search, color_coordinates))

        # Return the final list of color and coordinates tuples
        return color_coordinates_list

    @staticmethod
    def sublist(lst, n):
        """Sub lists of specific n number of elements"""
        return [lst[i : i + n] for i in range(0, len(lst), n)]

    @staticmethod
    def sublist_join(lst, n):
        """Join the lists in a unique list of n elements"""
        arr = np.array(lst)
        num_windows = len(lst) - n + 1
        result = [arr[i : i + n].tolist() for i in range(num_windows)]
        return result

    # The below functions are basically the same ech one
    # of them is allowing filtering and putting together in a
    # list the specific Layers, Paths, Zones and Pints in the
    # Vacuums Json in parallel.

    @staticmethod
    def find_layers(
        json_obj: JsonType, layer_dict: dict = None, active_list: list = None
    ) -> tuple[dict, list]:
        """Find the layers in the json object."""
        if layer_dict is None:
            layer_dict = {}
        if active_list is None:
            active_list = []
        if isinstance(json_obj, dict):
            if "__class" in json_obj and json_obj["__class"] == "MapLayer":
                layer_type = json_obj.get("type")
                active_type = json_obj.get("metaData")
                if layer_type:
                    if layer_type not in layer_dict:
                        layer_dict[layer_type] = []
                    layer_dict[layer_type].append(json_obj.get("compressedPixels", []))
                if layer_type == "segment":
                    active_list.append(int(active_type["active"]))

            for value in json_obj.items():
                ImageData.find_layers(value, layer_dict, active_list)
        elif isinstance(json_obj, list):
            for item in json_obj:
                ImageData.find_layers(item, layer_dict, active_list)
        return layer_dict, active_list

    @staticmethod
    def find_points_entities(json_obj: JsonType, entity_dict: dict = None) -> dict:
        """Find the points entities in the json object."""
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
    def find_paths_entities(json_obj: JsonType, entity_dict: dict = None) -> dict:
        """Find the paths entities in the json object."""

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
    def find_zone_entities(json_obj: JsonType, entity_dict: dict = None) -> dict:
        """Find the zone entities in the json object."""
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
    def find_virtual_walls(json_obj: JsonType) -> list:
        """Find the virtual walls in the json object."""
        virtual_walls = []

        def find_virtual_walls_recursive(obj):
            """Find the virtual walls in the json object recursively."""
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

    @staticmethod
    async def async_get_rooms_coordinates(
        pixels: list, pixel_size: int = 5, rand: bool = False
    ) -> tuple:
        """
        Extract the room coordinates from the vacuum pixels data.
        piexels: dict: The pixels data format [[x,y,z], [x1,y1,z1], [xn,yn,zn]].
        pixel_size: int: The size of the pixel in mm (optional).
        rand: bool: Return the coordinates in a rand256 format (optional).
        """
        # Initialize variables to store max and min coordinates
        max_x, max_y = pixels[0][0], pixels[0][1]
        min_x, min_y = pixels[0][0], pixels[0][1]
        # Iterate through the data list to find max and min coordinates
        for entry in pixels:
            if rand:
                x, y, _ = entry  # Extract x and y coordinates
                max_x = max(max_x, x)  # Update max x coordinate
                max_y = max(max_y, y + pixel_size)  # Update max y coordinate
                min_x = min(min_x, x)  # Update min x coordinate
                min_y = min(min_y, y)  # Update min y coordinate
            else:
                x, y, z = entry  # Extract x and y coordinates
                max_x = max(max_x, x + z)  # Update max x coordinate
                max_y = max(max_y, y + pixel_size)  # Update max y coordinate
                min_x = min(min_x, x)  # Update min x coordinate
                min_y = min(min_y, y)  # Update min y coordinate
        if rand:
            return (
                (((max_x * pixel_size) * 10), ((max_y * pixel_size) * 10)),
                (
                    ((min_x * pixel_size) * 10),
                    ((min_y * pixel_size) * 10),
                ),
            )
        else:
            return (
                min_x * pixel_size,
                min_y * pixel_size,
                max_x * pixel_size,
                max_y * pixel_size,
            )

    # Added below in order to support Valetudo Re.
    # This functions read directly the data from the json created
    # from the parser for Valetudo Re. They allow to use the
    # functions to draw the image without changes on the drawing class.

    @staticmethod
    def from_rrm_to_compressed_pixels(
        pixel_data: list,
        image_width: int = 0,
        image_height: int = 0,
        image_top: int = 0,
        image_left: int = 0,
    ) -> list:
        """Convert the pixel data to compressed pixels."""
        compressed_pixels = []

        tot_pixels = 0
        current_x, current_y, count = None, None, 0
        for index in pixel_data:
            x = (index % image_width) + image_left
            y = ((image_height - 1) - (index // image_width)) + image_top

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
        """Calculate the max and min x and y coordinates."""
        max_x = -float("inf")
        max_y = -float("inf")

        for x, y, count in coord_array:
            max_x = max(max_x, x)
            max_y = max(max_y, y)

        return (max_x * 6), (max_y * 6)

    @staticmethod
    def rrm_coordinates_to_valetudo(points):
        """Transform the coordinates from RRM to Valetudo."""
        transformed_points = []
        dimension_mm = 50 * 1024
        for i, p in enumerate(points):
            if i % 2 == 0:
                transformed_points.append(round(p / 10))
            else:
                transformed_points.append(round((dimension_mm - p) / 10))
        return transformed_points

    @staticmethod
    def rrm_valetudo_path_array(points):
        """Transform the path coordinates from RRM to Valetudo."""
        transformed_points = []
        for point in points:
            transformed_x = round(point[0] / 10)
            transformed_y = round(point[1] / 10)
            transformed_points.extend([[transformed_x, transformed_y]])
        return transformed_points

    @staticmethod
    def get_rrm_image(json_data: JsonType) -> JsonType:
        """Get the image data from the json."""
        if isinstance(json_data, tuple):
            return {}
        else:
            return json_data.get("image", {})

    @staticmethod
    def get_rrm_path(json_data: JsonType) -> JsonType:
        """Get the path data from the json."""
        return json_data.get("path", {})

    @staticmethod
    def get_rrm_goto_predicted_path(json_data: JsonType) -> list or None:
        """Get the predicted path data from the json."""
        try:
            predicted_path = json_data.get("goto_predicted_path", {})
            points = predicted_path["points"]
        except KeyError:
            return None
        else:
            predicted_path = ImageData.sublist_join(
                ImageData.rrm_valetudo_path_array(points), 2
            )
        return predicted_path

    @staticmethod
    def get_rrm_charger_position(json_data: JsonType) -> JsonType:
        """Get the charger position from the json."""
        return json_data.get("charger", {})

    @staticmethod
    def get_rrm_robot_position(json_data: JsonType) -> JsonType:
        """Get the robot position from the json."""
        return json_data.get("robot", {})

    @staticmethod
    def get_rrm_robot_angle(json_data: JsonType) -> tuple:
        """
        Get the robot angle from the json.
        Return the calculated angle and original angle.
        """
        angle_c = round(json_data.get("robot_angle", 0))
        if angle_c < 0:
            angle = (360 - angle_c) + 80
        else:
            angle = (180 - angle_c) - 80
        return angle % 360, json_data.get("robot_angle", 0)

    @staticmethod
    def get_rrm_goto_target(json_data: JsonType) -> list or None:
        """Get the goto target from the json."""
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
    def get_rrm_currently_cleaned_zones(json_data: JsonType) -> dict:
        """Get the currently cleaned zones from the json."""
        re_zones = json_data.get("currently_cleaned_zones", [])
        formatted_zones = ImageData.rrm_valetudo_format_zone(re_zones)
        return formatted_zones

    @staticmethod
    def get_rrm_forbidden_zones(json_data: JsonType) -> dict:
        """Get the forbidden zones from the json."""
        re_zones = json_data.get("forbidden_zones", [])
        formatted_zones = ImageData.rrm_valetudo_format_zone(re_zones)
        return formatted_zones

    @staticmethod
    def rrm_valetudo_format_zone(coordinates: list) -> any:
        """Format the zones from RRM to Valetudo."""
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
    def rrm_valetudo_lines(coordinates: list) -> list:
        """Format the lines from RRM to Valetudo."""
        formatted_lines = []
        for lines in coordinates:
            line = [lines[0] // 10, lines[1] // 10, lines[2] // 10, lines[3] // 10]
            formatted_lines.append(line)
        return formatted_lines

    @staticmethod
    def get_rrm_virtual_walls(json_data: JsonType) -> list or None:
        """Get the virtual walls from the json."""
        try:
            tmp_data = json_data.get("virtual_walls", [])
        except KeyError:
            return None
        virtual_walls = ImageData.rrm_valetudo_lines(tmp_data)
        return virtual_walls

    @staticmethod
    def get_rrm_currently_cleaned_blocks(json_data: JsonType) -> list:
        """Get the currently cleaned blocks from the json."""
        return json_data.get("currently_cleaned_blocks", [])

    @staticmethod
    def get_rrm_forbidden_mop_zones(json_data: JsonType) -> list:
        """Get the forbidden mop zones from the json."""
        return json_data.get("forbidden_mop_zones", [])

    @staticmethod
    def get_rrm_image_size(json_data: JsonType) -> ImageSize:
        """Get the image size from the json."""
        if isinstance(json_data, tuple):
            return 0, 0
        else:
            image = ImageData.get_rrm_image(json_data)
            if image == {}:
                return 0, 0
            dimensions = image.get("dimensions", {})
            return dimensions.get("width", 0), dimensions.get("height", 0)

    @staticmethod
    def get_rrm_image_position(json_data: JsonType) -> tuple:
        """Get the image position from the json."""
        image = ImageData.get_rrm_image(json_data)
        position = image.get("position", {})
        return position.get("top", 0), position.get("left", 0)

    @staticmethod
    def get_rrm_floor(json_data: JsonType) -> list:
        """Get the floor data from the json."""
        img = ImageData.get_rrm_image(json_data)
        return img.get("pixels", {}).get("floor", [])

    @staticmethod
    def get_rrm_walls(json_data: JsonType) -> list:
        """Get the walls data from the json."""
        img = ImageData.get_rrm_image(json_data)
        return img.get("pixels", {}).get("walls", [])

    @staticmethod
    async def async_get_rrm_segments(
        json_data, size_x, size_y, pos_top, pos_left, out_lines: bool = False
    ):
        """Get the segments data from the json."""

        img = ImageData.get_rrm_image(json_data)
        seg_data = img.get("segments", {})
        seg_ids = seg_data.get("id")
        segments = []
        outlines = []
        count_seg = 0
        for id_seg in seg_ids:
            tmp_data = seg_data.get("pixels_seg_" + str(id_seg))
            segments.append(
                ImageData.from_rrm_to_compressed_pixels(
                    tmp_data,
                    image_width=size_x,
                    image_height=size_y,
                    image_top=pos_top,
                    image_left=pos_left,
                )
            )
            if out_lines:
                room_coords = await ImageData.async_get_rooms_coordinates(
                    pixels=segments[count_seg], rand=True
                )
                outlines.append(room_coords)
                count_seg += 1
        if count_seg > 0:
            if out_lines:
                return segments, outlines
            else:
                return segments
        else:
            return []

    @staticmethod
    def get_rrm_segments_ids(json_data: JsonType) -> list or None:
        """Get the segments ids from the json."""
        try:
            img = ImageData.get_rrm_image(json_data)
            seg_ids = img.get("segments", {}).get("id", [])
        except KeyError:
            return None
        return seg_ids

    @staticmethod
    def convert_negative_angle(angle: int) -> int:
        """Convert negative angle to positive."""
        angle_c = angle % 360  # Ensure angle is within 0-359
        if angle_c < 0:
            angle_c += 360  # Convert negative angle to positive
        angle = angle_c + 180  # add offset
        return angle

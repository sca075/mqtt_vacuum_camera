"""
Image Handler Module.
It returns the PIL PNG image frame relative to the Map Data extrapolated from the vacuum json.
It also returns calibration, rooms data to the card and other images information to the camera.
Last Changed on Version: 1.5.5
"""
from __future__ import annotations

import logging
import numpy as np
import hashlib
import json
from PIL import Image

from custom_components.valetudo_vacuum_camera.utils.colors_man import color_grey
from custom_components.valetudo_vacuum_camera.types import Color, Colors
from custom_components.valetudo_vacuum_camera.utils.img_data import ImageData
from custom_components.valetudo_vacuum_camera.utils.draweble import Drawable


_LOGGER = logging.getLogger(__name__)


# noinspection PyTypeChecker,PyUnboundLocalVariable
class MapImageHandler(object):
    def __init__(self):
        self.auto_crop = None
        self.calibration_data = None
        self.charger_pos = None
        self.crop_area = None
        self.crop_img_size = None
        self.data = ImageData
        self.draw = Drawable
        self.frame_number = 0
        self.go_to = None
        self.img_hash = None
        self.img_base_layer = None
        self.img_rotate = 0
        self.img_size = None
        self.json_data = None
        self.json_id = None
        self.path_pixels = None
        self.robot_in_room = None
        self.robot_pos = None
        self.room_propriety = None
        self.rooms_pos = None
        self.trim_down = None
        self.trim_left = None
        self.trim_right = None
        self.trim_up = None

    async def auto_crop_and_trim_array(
            self,
            image_array,
            detect_colour,
            margin_size: int = 0,
            rotate: int = 0,
    ):
        """
        Automatically crops and trims a numpy array and returns the processed image.
        """
        if not self.auto_crop:
            _LOGGER.debug(f"Image original size: {image_array.shape[1]}, {image_array.shape[0]}")
            center_x = image_array.shape[1] // 2
            center_y = image_array.shape[0] // 2
            # Find the coordinates of the first occurrence of a non-background color
            nonzero_coords = np.column_stack(np.where(image_array != list(detect_colour)))
            # Calculate the crop box based on the first and last occurrences
            min_y, min_x, dummy = np.min(nonzero_coords, axis=0)
            max_y, max_x, dummy = np.max(nonzero_coords, axis=0)
            del dummy, nonzero_coords
            _LOGGER.debug("Found crop max and min values (y,x) ({}, {}) ({},{})...".format(
                int(max_y), int(max_x), int(min_y), int(min_x)))
            # Calculate and store the trims coordinates with margins
            self.trim_left = int(min_x) - margin_size
            self.trim_up = int(min_y) - margin_size
            self.trim_right = int(max_x) + margin_size
            self.trim_down = int(max_y) + margin_size
            del min_y, min_x, max_x, max_y
            _LOGGER.debug("Calculated trims coordinates right {}, bottom {}, left {}, up {} ".format(
                self.trim_right, self.trim_down, self.trim_left, self.trim_up))
            # Calculate the dimensions after trimming using min/max values
            trimmed_width = max(0,  self.trim_right - self.trim_left)
            trimmed_height = max(0, self.trim_down - self.trim_up)
            trim_r = image_array.shape[1] - self.trim_right
            trim_d = image_array.shape[0] - self.trim_down
            trim_l = image_array.shape[1] - self.trim_left
            trim_u = image_array.shape[0] - self.trim_up
            _LOGGER.debug("Calculated trims values for right {}, bottom {}, left {} and up {}.".format(
                trim_r, trim_d, trim_l, trim_u))
            _LOGGER.debug("Calculated trim width {} and trim height {}".format(trimmed_width, trimmed_height))
            # Test if the trims are okay or not
            if trimmed_height <= margin_size or trimmed_width <= margin_size:
                _LOGGER.debug(f"Background colour not detected at rotation {rotate}.")
                pos_0 = 0
                self.crop_area = (pos_0, pos_0, image_array.shape[1], image_array.shape[0])
                self.img_size = (image_array.shape[1], image_array.shape[0])
                del trimmed_width, trimmed_height
                return image_array
            # Calculate the cropping sizes after that the trim is apply
            crop_area = trimmed_height * trimmed_width
            origin_area = image_array.shape[1] * image_array.shape[0]
            crop_percentage = (100 - round((origin_area / crop_area), 2))
            crop_size = (int(min(center_x, center_y) * crop_percentage) / 100) / 100
            _LOGGER.debug("Calculated image reduction of {:.2f}% with crop size {:.2f}%".format(crop_percentage,
                                                                                                crop_size))
            del crop_size, crop_percentage, origin_area, crop_area, trimmed_width, trimmed_height
            del center_x, center_y, trim_d, trim_u, trim_l, trim_r
            # Store Crop area of the original image_array we will use from the next frame.
            self.auto_crop = (
                self.trim_left,
                self.trim_up,
                self.trim_right,
                self.trim_down,
            )
        # Apply the auto-calculated trims to the rotated image
        trimmed = image_array[
                  self.auto_crop[1]: self.auto_crop[3],
                  self.auto_crop[0]: self.auto_crop[2]
                  ]
        del image_array
        # Rotate the cropped image based on the given angle
        if rotate == 90:
            rotated = np.rot90(trimmed, 1)
            self.crop_area = (
                self.trim_left,
                self.trim_up,
                self.trim_right,
                self.trim_down
            )
        elif rotate == 180:
            rotated = np.rot90(trimmed, 2)
            self.crop_area = self.auto_crop
        elif rotate == 270:
            rotated = np.rot90(trimmed, 3)
            self.crop_area = (
                self.trim_left,
                self.trim_up,
                self.trim_right,
                self.trim_down
            )
        else:
            rotated = trimmed
            self.crop_area = self.auto_crop
        del trimmed
        _LOGGER.debug(f"Auto Crop and Trim Box data: {self.crop_area}")
        self.crop_img_size = (rotated.shape[1], rotated.shape[0])
        _LOGGER.debug(f"Auto Crop and Trim image size: {self.crop_img_size}")
        return rotated

    def extract_room_properties(self, json_data):
        room_properties = {}
        self.rooms_pos = []
        pixel_size = json_data.get("pixelSize", [])

        for layer in json_data.get("layers", []):
            if layer["__class"] == "MapLayer":
                meta_data = layer.get("metaData", {})
                segment_id = meta_data.get("segmentId")

                if segment_id is not None:
                    name = meta_data.get("name")
                    # Calculate x and y min/max from compressed pixels
                    x_min = min(layer["compressedPixels"][::3]) * pixel_size
                    x_max = max(layer["compressedPixels"][::3]) * pixel_size
                    y_min = min(layer["compressedPixels"][1::3]) * pixel_size
                    y_max = max(layer["compressedPixels"][1::3]) * pixel_size
                    corners = [(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)]
                    room_id = str(segment_id)
                    self.rooms_pos.append(
                        {
                            "name": name,
                            "corners": corners,
                        }
                    )
                    room_properties[room_id] = {
                        "number": segment_id,
                        "outline": corners,
                        "name": name,
                        "x": ((x_min + x_max) // 2),
                        "y": ((y_min + y_max) // 2),
                    }
        if room_properties != {}:
            _LOGGER.debug("Rooms data extracted!")
        else:
            _LOGGER.debug("Rooms data not available!")
            self.rooms_pos = None
        return room_properties

    async def get_image_from_json(
            self,
            m_json,
            robot_state,
            img_rotation: int = 0,
            margins: int = 0,
            user_colors: Colors = None,
            rooms_colors: Color = None,
            file_name: "" = None,
            drawing_limit: float = 0.0,
    ):

        color_wall: Color = user_colors[0]
        color_no_go: Color = user_colors[6]
        color_go_to: Color = user_colors[7]
        color_robot: Color = user_colors[2]
        color_charger: Color = user_colors[5]
        color_move: Color = user_colors[4]
        color_background: Color = user_colors[3]
        color_zone_clean: Color = user_colors[1]

        try:
            if m_json is not None:
                _LOGGER.info(f"{file_name}: Composing the image for the camera.")
                # buffer json data
                self.json_data = m_json

                if self.room_propriety and self.frame_number == 0:
                    _LOGGER.info(f"{file_name}: Supporting Rooms Cleaning!")

                size_x = int(m_json["size"]["x"])
                size_y = int(m_json["size"]["y"])
                self.img_size = {
                    "x": size_x,
                    "y": size_y,
                    "centre": [(size_x // 2), (size_y // 2)],
                }

                try:
                    self.json_id = m_json["metaData"]["nonce"]
                except (ValueError, KeyError) as e:
                    _LOGGER.debug(f"No JsonID provided: {e}")
                    self.json_id = None
                else:
                    _LOGGER.info(f"Vacuum JSon ID: {self.json_id} at Frame {self.frame_number}.")

                predicted_path = None
                path_pixels = None
                predicted_pat2 = None
                try:
                    paths_data = self.data.find_paths_entities(m_json, None)
                    predicted_path = paths_data.get("predicted_path", [])
                    path_pixels = paths_data.get("path", [])
                except KeyError as e:
                    _LOGGER.info(
                        f"{file_name}: Error extracting paths data: {str(e)}"
                    )
                if predicted_path:
                    predicted_path = predicted_path[0]["points"]
                    predicted_path = self.data.sublist(predicted_path, 2)
                    predicted_pat2 = self.data.sublist_join(predicted_path, 2)

                try:
                    zone_clean = self.data.find_zone_entities(m_json, None)
                except (ValueError, KeyError) as e:
                    _LOGGER.info(f"{file_name}: No zones: {str(e)}")
                    zone_clean = None
                else:
                    _LOGGER.debug(f"{file_name}: Got zones: {zone_clean}")

                try:
                    virtual_walls = self.data.find_virtual_walls(m_json)
                except (ValueError, KeyError) as e:
                    _LOGGER.info(f"{file_name}: No virtual walls: {str(e)}")
                    virtual_walls = None
                else:
                    _LOGGER.debug(f"{file_name}: Got virtual walls: {virtual_walls}")

                try:
                    entity_dict = self.data.find_points_entities(m_json, None)
                except (ValueError, KeyError) as e:
                    _LOGGER.warning(f"{file_name}: No points in json data: {str(e)}")
                    entity_dict = None
                else:
                    _LOGGER.debug(
                        f"{file_name}: Got the points in the json: {entity_dict}"
                    )

                robot_position_angle = None
                robot_position = None
                robot_pos = None
                if entity_dict:
                    try:
                        robot_pos = entity_dict.get("robot_position")
                    except KeyError:
                        _LOGGER.warning("No robot position found.")
                    else:
                        if robot_pos:
                            robot_position = robot_pos[0]["points"]
                            robot_position_angle = robot_pos[0]["metaData"]["angle"]
                            if self.rooms_pos is None:
                                self.robot_pos = {
                                    "x": robot_position[0],
                                    "y": robot_position[1],
                                    "angle": robot_position_angle,
                                }
                            else:
                                self.robot_pos = await self.get_robot_in_room(
                                    (robot_position[1]),
                                    (robot_position[0]),
                                    robot_position_angle)

                            _LOGGER.debug(f"Robot Position: {list(self.robot_pos.items())}")

                charger_pos = None
                if entity_dict:
                    try:
                        charger_pos = entity_dict.get("charger_location")
                    except KeyError:
                        _LOGGER.warning("No charger position found.")
                    else:
                        if charger_pos:
                            charger_pos = charger_pos[0]["points"]
                            self.charger_pos = {
                                "x": charger_pos[0],
                                "y": charger_pos[1],
                            }
                        _LOGGER.debug(f"Charger Position: {list(self.charger_pos.items())}")

                if entity_dict:
                    try:
                        obstacle_data = entity_dict.get("obstacle")
                    except KeyError:
                        _LOGGER.info("No obstacle found.")
                    else:
                        obstacle_positions = []
                        if obstacle_data:
                            for obstacle in obstacle_data:
                                label = obstacle.get("metaData", {}).get("label")
                                points = obstacle.get("points", [])

                                if label and points:
                                    obstacle_pos = {"label": label, "points": {"x": points[0], "y": points[1]}}
                                    obstacle_positions.append(obstacle_pos)

                        # List of dictionaries containing label and points for each obstacle
                        _LOGGER.debug("All obstacle positions: %s", obstacle_positions)

                go_to = entity_dict.get("go_to_target")
                pixel_size = int(m_json["pixelSize"])
                layers, active = self.data.find_layers(m_json["layers"])
                new_frame_hash = await self.calculate_array_hash(layers, active)
                if self.frame_number == 0:
                    self.img_hash = await self.calculate_array_hash(layers, active)
                    # The below is drawing the base layer that will be reused at the next frame.
                    _LOGGER.debug(f"{file_name}: Layers to draw: {layers.keys()}")
                    _LOGGER.info(f"{file_name}: Empty image with background color")
                    img_np_array = await self.draw.create_empty_image(size_x, size_y, color_background)
                    _LOGGER.info(f"{file_name}: Overlapping Layers")
                    room_id = 0
                    for layer_type, compressed_pixels_list in layers.items():
                        for compressed_pixels in compressed_pixels_list:
                            pixels = self.data.sublist(compressed_pixels, 3)
                            if layer_type == "segment" or layer_type == "floor":
                                room_color = rooms_colors[room_id]
                                if layer_type == "segment" or layer_type == "floor":
                                    room_color = rooms_colors[room_id]
                                if layer_type == "segment":
                                    # Check if the room is active and set a modified color
                                    if active and len(active) > room_id and active[room_id] == 1:
                                        room_color = (
                                            ((2 * room_color[0]) + color_zone_clean[0]) // 3,
                                            ((2 * room_color[1]) + color_zone_clean[1]) // 3,
                                            ((2 * room_color[2]) + color_zone_clean[2]) // 3,
                                            ((2 * room_color[3]) + color_zone_clean[3]) // 3
                                        )
                                img_np_array = await self.draw.from_json_to_image(
                                    img_np_array, pixels, pixel_size, room_color
                                )
                                if room_id < 15:
                                    room_id += 1
                                else:
                                    room_id = 0
                            elif layer_type == "wall":
                                # Drawing walls.
                                img_np_array = await self.draw.from_json_to_image(
                                    img_np_array, pixels, pixel_size, color_wall
                                )
                    if virtual_walls:
                        img_np_array = await self.draw.draw_virtual_walls(
                            img_np_array, virtual_walls, color_no_go
                        )
                    if zone_clean:
                        try:
                            no_go_zones = zone_clean.get("no_go_area")
                        except KeyError:
                            no_go_zones = None

                        try:
                            no_mop_zones = zone_clean.get("no_mop_area")
                        except KeyError:
                            no_mop_zones = None

                        if no_go_zones:
                            _LOGGER.info(f"{file_name}: Drawing No Go area.")
                            img_np_array = await self.draw.zones(
                                img_np_array, no_go_zones, color_no_go
                            )
                        if no_mop_zones:
                            _LOGGER.info(f"{file_name}: Drawing No Mop area.")
                            img_np_array = await self.draw.zones(
                                img_np_array, no_mop_zones, color_no_go
                            )
                    # charger
                    if charger_pos:
                        img_np_array = await self.draw.battery_charger(
                            img_np_array, charger_pos[0], charger_pos[1], color_charger
                        )

                    if obstacle_positions:
                        self.draw.draw_obstacles(img_np_array,
                                                 obstacle_positions,
                                                 color_no_go)

                    if (room_id > 0) and not self.room_propriety:
                        self.room_propriety = self.extract_room_properties(self.json_data)
                        if self.rooms_pos:
                            self.robot_pos = await self.get_robot_in_room(
                                (robot_position[1]),
                                (robot_position[0]),
                                robot_position_angle)

                    _LOGGER.info(f"{file_name}: Completed base Layers")
                    self.img_base_layer = await self.async_copy_array(img_np_array)

                self.frame_number += 1
                if (self.frame_number > 1024) or (new_frame_hash != self.img_hash):
                    self.frame_number = 0

                _LOGGER.debug(f"{file_name}: Frame number %s", self.frame_number)
                img_np_array = await self.async_copy_array(self.img_base_layer)
                # All below will be drawn each time
                # If there is a zone clean we draw it now.
                if zone_clean:
                    try:
                        zones_clean = zone_clean.get("active_zone")
                    except KeyError:
                        zones_clean = None
                    if zones_clean:
                        _LOGGER.info(f"{file_name}: Drawing Zone Clean.")
                        img_np_array = await self.draw.zones(
                            img_np_array, zones_clean, color_zone_clean
                        )

                if go_to:
                    img_np_array = await self.draw.go_to_flag(
                        img_np_array,
                        (go_to[0]["points"][0], go_to[0]["points"][1]),
                        self.img_rotate,
                        color_go_to,
                    )
                if predicted_pat2:
                    img_np_array = await self.draw.lines(
                        img_np_array, predicted_pat2, 2, color_grey
                    )
                # draw path
                if path_pixels:
                    for path in path_pixels:
                        # Get the points from the current path and extend the all_path_points list
                        points = path.get("points", [])
                        sublists = self.data.sublist(points, 2)
                        path_pixel2 = self.data.sublist_join(sublists, 2)
                        img_np_array = await self.draw.lines(
                            img_np_array, path_pixel2, 5, color_move
                        )
                if robot_state == "docked":
                    robot_position_angle = robot_position_angle - 180
                if robot_pos:
                    img_np_array = await self.draw.robot(
                        img_np_array,
                        robot_position[0],
                        robot_position[1],
                        robot_position_angle,
                        color_robot,
                        file_name,
                    )
                _LOGGER.debug(f"{file_name}: Auto cropping the image with rotation: {int(img_rotation)}")
                img_np_array = await self.auto_crop_and_trim_array(
                    img_np_array,
                    color_background,
                    int(margins),
                    int(img_rotation),
                )
                pil_img = Image.fromarray(img_np_array, mode="RGBA")
                del img_np_array
                return pil_img
        except Exception as e:
            _LOGGER.warning(f"{file_name} : Error in get_image_from_json: {e}", exc_info=True)
            return None

    def get_frame_number(self):
        return self.frame_number

    def get_robot_position(self):
        return self.robot_pos

    def get_charger_position(self):
        return self.charger_pos

    def get_img_size(self):
        return self.img_size

    def get_json_id(self):
        return self.json_id

    async def get_rooms_attributes(self):
        if self.room_propriety:
            return self.room_propriety
        if self.json_data:
            _LOGGER.debug("Checking for Rooms data..")
            self.room_propriety = self.extract_room_properties(self.json_data)
            if self.room_propriety:
                _LOGGER.debug("Got Rooms Attributes.")
        return self.room_propriety

    async def get_robot_in_room(self, robot_y, robot_x, angle):
        # do we know where we are?
        if self.robot_in_room:
            if (
                    ((self.robot_in_room["right"] >= int(robot_x)) and (self.robot_in_room["left"] <= int(robot_x)))
                    and ((self.robot_in_room["down"] >= int(robot_y)) and (self.robot_in_room["up"] <= int(robot_y)))
            ):
                temp = {
                    "x": robot_x,
                    "y": robot_y,
                    "angle": angle,
                    "in_room": self.robot_in_room["room"],
                }
                return temp
        # else we need to search and use the async method.
        _LOGGER.debug("The robot changed room.. searching..")
        for room in self.rooms_pos:
            corners = room["corners"]
            self.robot_in_room = {
                "left": int(corners[0][0]),
                "right": int(corners[2][0]),
                "up": int(corners[0][1]),
                "down": int(corners[2][1]),
                "room": room["name"],
            }
            # Check if the robot coordinates are inside the room's corners
            if (
                    ((self.robot_in_room["right"] >= int(robot_x)) and (self.robot_in_room["left"] <= int(robot_x)))
                    and ((self.robot_in_room["down"] >= int(robot_y)) and (self.robot_in_room["up"] <= int(robot_y)))
            ):
                temp = {
                    "x": robot_x,
                    "y": robot_y,
                    "angle": angle,
                    "in_room": self.robot_in_room["room"],
                }
                _LOGGER.debug(f"Robot is in {self.robot_in_room['room']}")
                del room, corners, robot_x, robot_y  # free memory.
                return temp
        del room, corners  # free memory.
        _LOGGER.debug("Robot not located in any Room")
        self.robot_in_room = None
        temp = {
            "x": robot_x,
            "y": robot_y,
            "angle": angle,
        }
        # If the robot is not inside any room, return None or a default value
        return temp

    def get_calibration_data(self, rotation_angle):
        calibration_data = []
        self.img_rotate = rotation_angle
        _LOGGER.info("Getting Calibrations points")
        # Calculate the calibration points in the vacuum coordinate system

        vacuum_points = [
            {"x": self.crop_area[0], "y": self.crop_area[1]},  # Top-left corner 0
            {"x": self.crop_area[2], "y": self.crop_area[1]},  # Top-right corner 1
            {"x": self.crop_area[2], "y": self.crop_area[3]},  # Bottom-right corner 2
            {
                "x": self.crop_area[0],
                "y": self.crop_area[3],
            },  # Bottom-left corner (optional)3
        ]

        # Define the map points (fixed)
        map_points = [
            {"x": 0, "y": 0},  # Top-left corner 0
            {"x": self.crop_img_size[0], "y": 0},  # Top-right corner 1
            {
                "x": self.crop_img_size[0],
                "y": self.crop_img_size[1],
            },  # Bottom-right corner 2
            {"x": 0, "y": self.crop_img_size[1]},  # Bottom-left corner (optional) 3
        ]

        # Rotate the vacuum points based on the rotation angle
        if rotation_angle == 90:
            vacuum_points = [
                vacuum_points[1],
                vacuum_points[2],
                vacuum_points[3],
                vacuum_points[0],
            ]
        elif rotation_angle == 180:
            vacuum_points = [
                vacuum_points[2],
                vacuum_points[3],
                vacuum_points[0],
                vacuum_points[1],
            ]
        elif rotation_angle == 270:
            vacuum_points = [
                vacuum_points[3],
                vacuum_points[0],
                vacuum_points[1],
                vacuum_points[2],
            ]

        # Create the calibration data for each point
        for vacuum_point, map_point in zip(vacuum_points, map_points):
            calibration_point = {"vacuum": vacuum_point, "map": map_point}
            calibration_data.append(calibration_point)

        return calibration_data

    async def async_copy_array(self, original_array):
        copied_array = np.copy(original_array)

        return copied_array

    # noinspection PyUnresolvedReferences
    async def calculate_array_hash(self, layers: None, active: None):
        if layers and active:
            data_to_hash = {
                'layers': len(layers["wall"][0]),
                'active_segments': tuple(active),
            }
            data_json = json.dumps(data_to_hash, sort_keys=True)
            hash_value = hashlib.sha256(data_json.encode()).hexdigest()
        else:
            hash_value = None
        return hash_value

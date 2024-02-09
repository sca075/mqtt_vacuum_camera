"""
Image Handler Module.
It returns the PIL PNG image frame relative to the Map Data extrapolated from the vacuum json.
It also returns calibration, rooms data to the card and other images information to the camera.
Last Changed on Version: 1.5.7.4
"""
from __future__ import annotations

import hashlib
import json
import logging

from PIL import Image
import numpy as np
from psutil_home_assistant import PsutilWrapper as ProcInspector
import svgwrite
from svgwrite import shapes

from custom_components.valetudo_vacuum_camera.types import Color
from custom_components.valetudo_vacuum_camera.utils.colors_man import color_grey
from custom_components.valetudo_vacuum_camera.utils.draweble import Drawable
from custom_components.valetudo_vacuum_camera.utils.img_data import ImageData

# import asyncio


_LOGGER = logging.getLogger(__name__)


# Custom exception for memory shortage
class MemoryShortageError(Exception):
    """Custom exception for memory shortage.
    :return: Exception message."""

    def __init__(self, message="Not enough memory available"):
        self.message = message
        super().__init__(self.message)


# noinspection PyTypeChecker,PyUnboundLocalVariable,PyUnresolvedReferences
class MapImageHandler(object):
    """Map Image Handler Class.
    This class is used to handle the image data and the drawing of the map."""

    MEMORY_WARN_LIMIT = 2  # Required memory for number of np.array's

    def __init__(self, shared_data):
        """Initialize the Map Image Handler."""
        self.auto_crop = None  # auto crop data to be calculate once.
        self.calibration_data = None  # camera shared data.
        self.charger_pos = None  # vacuum data charger position.
        self.crop_area = None  # module shared for calibration data.
        self.crop_img_size = None  # size of the image cropped calibration data.
        self.data = ImageData  # imported Image Data Module.
        self.draw = Drawable  # imported Drawing utilities
        self.frame_number = 0  # image frame number
        self.go_to = None  # vacuum go to data
        self.img_hash = None  # hash of the image calculated to check differences.
        self.img_base_layer = None  # numpy array store the map base layer.
        self.img_rotate = 0  # rotation to apply to the image.
        self.img_size = None  # size of the created image
        self.json_data = None  # local stored and shared json data.
        self.json_id = None  # grabbed data of the vacuum image id.
        self.path_pixels = None  # vacuum path datas.
        self.robot_in_room = None  # vacuum room position.
        self.robot_pos = None  # vacuum coordinates.
        self.room_propriety = None  # vacuum segments data.
        self.rooms_pos = None  # vacuum room coordinates / name list.
        self.shared = shared_data  # camera shared data.
        self.svg_wait = False  # SVG image creation wait.
        self.trim_down = None  # memory stored trims calculated once.
        self.trim_left = None  # memory stored trims calculated once.
        self.trim_right = None  # memory stored trims calculated once.
        self.trim_up = None  # memory stored trims calculated once.

    async def async_auto_crop_and_trim_array(
        self,
        image_array,
        detect_colour,
        margin_size: int = 0,
        rotate: int = 0,
    ):
        """
        Automatically crops and trims a numpy array and returns the processed image.
        """
        try:
            if not self.auto_crop:
                _LOGGER.debug(
                    f"{self.shared.file_name}: Image original size ({image_array.shape[1]}, {image_array.shape[0]})."
                )
                # Find the coordinates of the first occurrence of a non-background color
                nonzero_coords = np.column_stack(
                    np.where(image_array != list(detect_colour))
                )
                # Calculate the crop box based on the first and last occurrences
                min_y, min_x, dummy = np.min(nonzero_coords, axis=0)
                max_y, max_x, dummy = np.max(nonzero_coords, axis=0)
                del dummy, nonzero_coords
                _LOGGER.debug(
                    "{}: Found crop max and min values (y,x) ({}, {}) ({},{})...".format(
                        self.shared.file_name,
                        int(max_y),
                        int(max_x),
                        int(min_y),
                        int(min_x),
                    )
                )
                # Calculate and store the trims coordinates with margins
                self.trim_left = int(min_x) - margin_size
                self.trim_up = int(min_y) - margin_size
                self.trim_right = int(max_x) + margin_size
                self.trim_down = int(max_y) + margin_size
                del min_y, min_x, max_x, max_y
                _LOGGER.debug(
                    "{}: Calculated trims coordinates right {}, bottom {}, left {}, up {}.".format(
                        self.shared.file_name,
                        self.trim_right,
                        self.trim_down,
                        self.trim_left,
                        self.trim_up,
                    )
                )
                # Calculate the dimensions after trimming using min/max values
                trimmed_width = max(0, self.trim_right - self.trim_left)
                trimmed_height = max(0, self.trim_down - self.trim_up)
                _LOGGER.debug(
                    "{}: Calculated trimmed image width {} and height {}".format(
                        self.shared.file_name, trimmed_width, trimmed_height
                    )
                )
                # Test if the trims are okay or not
                if trimmed_height <= margin_size or trimmed_width <= margin_size:
                    _LOGGER.debug(
                        f"{self.shared.file_name}: Background colour not detected at rotation {rotate}."
                    )
                    pos_0 = 0
                    self.crop_area = (
                        pos_0,
                        pos_0,
                        image_array.shape[1],
                        image_array.shape[0],
                    )
                    self.img_size = (image_array.shape[1], image_array.shape[0])
                    del trimmed_width, trimmed_height
                    return image_array

                # Store Crop area of the original image_array we will use from the next frame.
                self.auto_crop = (
                    self.trim_left,
                    self.trim_up,
                    self.trim_right,
                    self.trim_down,
                )
            # Apply the auto-calculated trims to the rotated image
            trimmed = image_array[
                self.auto_crop[1] : self.auto_crop[3],
                self.auto_crop[0] : self.auto_crop[2],
            ]
            del image_array
            # Rotate the cropped image based on the given angle
            if rotate == 90:
                rotated = np.rot90(trimmed, 1)
                self.crop_area = (
                    self.trim_left,
                    self.trim_up,
                    self.trim_right,
                    self.trim_down,
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
                    self.trim_down,
                )
            else:
                rotated = trimmed
                self.crop_area = self.auto_crop
            del trimmed
            _LOGGER.debug(
                f"{self.shared.file_name}: Auto Crop and Trim Box data: {self.crop_area}"
            )
            self.crop_img_size = (rotated.shape[1], rotated.shape[0])
            _LOGGER.debug(
                f"{self.shared.file_name}: Auto Crop and Trim image size: {self.crop_img_size}"
            )
        except Exception as e:
            _LOGGER.error(
                f"{self.shared.file_name}: Error {e} during auto crop and trim.",
                exc_info=True,
            )
            return None
        return rotated

    def extract_room_properties(self, json_data):
        """Extract room properties from the JSON data."""

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
                    corners = [
                        (x_min, y_min),
                        (x_max, y_min),
                        (x_max, y_max),
                        (x_min, y_max),
                    ]
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
            _LOGGER.debug(f"{self.shared.file_name}: Rooms data extracted!")
        else:
            _LOGGER.debug(f"{self.shared.file_name}: Rooms data not available!")
            self.rooms_pos = None
        return room_properties

    async def async_get_image_from_json(
        self,
        m_json,
    ):
        """Get the image from the JSON data.
        :param m_json: The JSON data from the Vacuum."""
        # Initialize the colors.
        color_wall: Color = self.shared.user_colors[0]
        color_no_go: Color = self.shared.user_colors[6]
        color_go_to: Color = self.shared.user_colors[7]
        color_robot: Color = self.shared.user_colors[2]
        color_charger: Color = self.shared.user_colors[5]
        color_move: Color = self.shared.user_colors[4]
        color_background: Color = self.shared.user_colors[3]
        color_zone_clean: Color = self.shared.user_colors[1]

        try:
            if m_json is not None:
                _LOGGER.info(
                    f"{self.shared.file_name}: Composing the image for the camera."
                )
                # buffer json data
                self.json_data = m_json

                if self.room_propriety and self.frame_number == 0:
                    _LOGGER.info(f"{self.shared.file_name}: Supporting Rooms Cleaning!")

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
                    _LOGGER.info(
                        f"Vacuum JSon ID: {self.json_id} at Frame {self.frame_number}."
                    )

                predicted_path = None
                path_pixels = None
                predicted_pat2 = None
                try:
                    paths_data = self.data.find_paths_entities(m_json, None)
                    predicted_path = paths_data.get("predicted_path", [])
                    path_pixels = paths_data.get("path", [])
                except KeyError as e:
                    _LOGGER.info(
                        f"{self.shared.file_name}: Error extracting paths data: {str(e)}"
                    )
                if predicted_path:
                    predicted_path = predicted_path[0]["points"]
                    predicted_path = self.data.sublist(predicted_path, 2)
                    predicted_pat2 = self.data.sublist_join(predicted_path, 2)

                try:
                    zone_clean = self.data.find_zone_entities(m_json, None)
                except (ValueError, KeyError):
                    zone_clean = None
                else:
                    _LOGGER.debug(f"{self.shared.file_name}: Got zones: {zone_clean}")

                try:
                    virtual_walls = self.data.find_virtual_walls(m_json)
                except (ValueError, KeyError):
                    virtual_walls = None
                else:
                    _LOGGER.debug(
                        f"{self.shared.file_name}: Got virtual walls: {virtual_walls}"
                    )

                try:
                    entity_dict = self.data.find_points_entities(m_json, None)
                except (ValueError, KeyError):
                    entity_dict = None
                else:
                    _LOGGER.debug(
                        f"{self.shared.file_name}: Got the points in the json: {entity_dict}"
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
                            robot_position_angle = round(
                                float(robot_pos[0]["metaData"]["angle"]), 1
                            )
                            if self.rooms_pos is None:
                                self.robot_pos = {
                                    "x": robot_position[0],
                                    "y": robot_position[1],
                                    "angle": robot_position_angle,
                                }
                            else:
                                self.robot_pos = await self.async_get_robot_in_room(
                                    robot_y=(robot_position[1]),
                                    robot_x=(robot_position[0]),
                                    angle=robot_position_angle,
                                )

                            _LOGGER.debug(
                                f"{self.shared.file_name} Position: {list(self.robot_pos.items())}"
                            )

                charger_pos = None
                if entity_dict:
                    try:
                        charger_pos = entity_dict.get("charger_location")
                    except KeyError:
                        _LOGGER.warning(
                            f"{self.shared.file_name}: No charger position found."
                        )
                    else:
                        if charger_pos:
                            charger_pos = charger_pos[0]["points"]
                            self.charger_pos = {
                                "x": charger_pos[0],
                                "y": charger_pos[1],
                            }
                        _LOGGER.debug(
                            f"Charger Position: {list(self.charger_pos.items())} of {self.shared.file_name}"
                        )

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
                                    obstacle_pos = {
                                        "label": label,
                                        "points": {"x": points[0], "y": points[1]},
                                    }
                                    obstacle_positions.append(obstacle_pos)

                        # List of dictionaries containing label and points for each obstacle
                        _LOGGER.debug("All obstacle positions: %s", obstacle_positions)

                go_to = entity_dict.get("go_to_target")
                pixel_size = int(m_json["pixelSize"])
                layers, active = self.data.find_layers(m_json["layers"])
                new_frame_hash = await self.calculate_array_hash(layers, active)
                if self.frame_number == 0:
                    self.img_hash = new_frame_hash
                    # The below is drawing the base layer that will be reused at the next frame.
                    _LOGGER.debug(
                        f"{self.shared.file_name}: Layers to draw: {layers.keys()}"
                    )
                    _LOGGER.info(
                        f"{self.shared.file_name}: Empty image with background color"
                    )
                    img_np_array = await self.draw.create_empty_image(
                        size_x, size_y, color_background
                    )
                    _LOGGER.info(f"{self.shared.file_name}: Overlapping Layers")
                    room_id = 0
                    rooms_list = [color_wall]
                    for layer_type, compressed_pixels_list in layers.items():
                        for compressed_pixels in compressed_pixels_list:
                            pixels = self.data.sublist(compressed_pixels, 3)
                            if layer_type == "segment" or layer_type == "floor":
                                room_color = self.shared.rooms_colors[room_id]
                                if layer_type == "segment" or layer_type == "floor":
                                    room_color = self.shared.rooms_colors[room_id]
                                    rooms_list.append(room_color)
                                if layer_type == "segment":
                                    # Check if the room is active and set a modified color
                                    if (
                                        active
                                        and len(active) > room_id
                                        and active[room_id] == 1
                                    ):
                                        room_color = (
                                            ((2 * room_color[0]) + color_zone_clean[0])
                                            // 3,
                                            ((2 * room_color[1]) + color_zone_clean[1])
                                            // 3,
                                            ((2 * room_color[2]) + color_zone_clean[2])
                                            // 3,
                                            ((2 * room_color[3]) + color_zone_clean[3])
                                            // 3,
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
                            _LOGGER.info(
                                f"{self.shared.file_name}: Drawing No Go area."
                            )
                            img_np_array = await self.draw.zones(
                                img_np_array, no_go_zones, color_no_go
                            )
                        if no_mop_zones:
                            _LOGGER.info(
                                f"{self.shared.file_name}: Drawing No Mop area."
                            )
                            img_np_array = await self.draw.zones(
                                img_np_array, no_mop_zones, color_no_go
                            )
                    # charger
                    if charger_pos:
                        img_np_array = await self.draw.battery_charger(
                            img_np_array, charger_pos[0], charger_pos[1], color_charger
                        )

                    if obstacle_positions:
                        self.draw.draw_obstacles(
                            img_np_array, obstacle_positions, color_no_go
                        )

                    if (room_id > 0) and not self.room_propriety:
                        self.room_propriety = self.extract_room_properties(
                            self.json_data
                        )
                        if self.rooms_pos:
                            self.robot_pos = await self.async_get_robot_in_room(
                                robot_x=(robot_position[0]),
                                robot_y=(robot_position[1]),
                                angle=robot_position_angle,
                            )

                    _LOGGER.info(f"{self.shared.file_name}: Completed base Layers")
                    self.img_base_layer = await self.async_copy_array(img_np_array)
                    if self.shared.export_svg and self.frame_number == 0:
                        # loop = asyncio.get_event_loop()
                        # svg_img = asyncio.run_coroutine_threadsafe(
                        #         self.async_numpy_array_to_svg(
                        #             base_layer=self.img_base_layer,
                        #             colours_list=rooms_list,
                        #             color_background=color_background
                        #         ),
                        #         loop
                        #     )
                        self.shared.export_svg = False
                        self.svg_wait = True
                    else:
                        self.svg_wait = False
                self.frame_number += 1
                if (self.frame_number > 1024) or (new_frame_hash != self.img_hash):
                    self.frame_number = 0
                _LOGGER.debug(
                    f"{self.shared.file_name}: Frame number %s", self.frame_number
                )
                try:
                    self.check_memory_with_margin(self.img_base_layer)
                except MemoryShortageError as e:
                    _LOGGER.warning(f"Memory shortage error: {e}")
                    return None
                img_np_array = await self.async_copy_array(self.img_base_layer)
                # All below will be drawn each time
                # If there is a zone clean we draw it now.
                if zone_clean:
                    try:
                        zones_clean = zone_clean.get("active_zone")
                    except KeyError:
                        zones_clean = None
                    if zones_clean:
                        _LOGGER.info(f"{self.shared.file_name}: Drawing Zone Clean.")
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
                if self.shared.vacuum_state == "docked":
                    robot_position_angle = robot_position_angle - 180
                if robot_pos:
                    img_np_array = await self.draw.robot(
                        layers=img_np_array,
                        x=robot_position[0],
                        y=robot_position[1],
                        angle=robot_position_angle,
                        fill=color_robot,
                        log=self.shared.file_name,
                    )
                _LOGGER.debug(
                    f"{self.shared.file_name}: Auto cropping the image with rotation:"
                    f" {int(self.shared.image_rotate)}"
                )
                img_np_array = await self.async_auto_crop_and_trim_array(
                    img_np_array,
                    color_background,
                    int(self.shared.margins),
                    int(self.shared.image_rotate),
                )
            if img_np_array is None:
                _LOGGER.warning(f"{self.shared.file_name}: Image array is None.")
                return None
            # Convert the numpy array to a PIL image
            pil_img = Image.fromarray(img_np_array, mode="RGBA")
            if self.svg_wait and self.frame_number == 1:
                # svg_img.result(90)
                # svg_img.add_done_callback(lambda future: future.result())
                self.svg_wait = False
            del img_np_array
            return pil_img
        except Exception as e:
            _LOGGER.warning(
                f"{self.shared.file_name} : Error in get_image_from_json: {e}",
                exc_info=True,
            )
            return None

    def get_frame_number(self):
        """Return the frame number of the image."""
        return self.frame_number

    def get_robot_position(self):
        """Return the robot position."""
        return self.robot_pos

    def get_charger_position(self):
        """Return the charger position."""
        return self.charger_pos

    def get_img_size(self):
        """Return the size of the image."""
        return self.img_size

    def get_json_id(self):
        """Return the JSON ID from the image."""
        return self.json_id

    def calculate_memory_usage(self, array: np.ndarray, margin: int) -> float:
        """Calculate the memory usage of the array.
        summing the memory usage of the arrays that will be used.
        The Numpy array shape is (y, x, 4) where 4 is the RGBA channels.
        Generally 1 pixel is 16 bytes.
        """
        element_size_bytes = array.itemsize * 4  # int32 is 4 bytes
        total_memory_bytes = array.size * element_size_bytes
        total_memory_mb = round(((margin * total_memory_bytes) / (1024 * 1024)), 1)
        _LOGGER.debug(f"{self.shared.file_name}: Estimated Margin of Memory usage: {total_memory_mb} MiB")
        return total_memory_mb

    # Function to check if there is enough available memory with a margin
    def check_memory_with_margin(self, array, margin=MEMORY_WARN_LIMIT):
        """Check if there is enough available memory with a margin.
        :raises MemoryShortageError: If there is not enough memory available."""
        array_memory_mb = self.calculate_memory_usage(array, margin)
        available_memory_mb = round(
            ProcInspector().psutil.virtual_memory().available / (1024 * 1024), 1
        )
        _LOGGER.debug(
            f"{self.shared.file_name}: Available memory: {available_memory_mb} MiB"
        )
        if available_memory_mb < array_memory_mb:
            raise MemoryShortageError(
                f"Not enough memory available (Margin: {array_memory_mb} MiB)"
            )

    async def async_get_rooms_attributes(self):
        """Get the rooms attributes from the JSON data.
        :return: The rooms attributes."""
        if self.room_propriety:
            return self.room_propriety
        if self.json_data:
            _LOGGER.debug(f"Checking {self.shared.file_name} Rooms data..")
            self.room_propriety = self.extract_room_properties(self.json_data)
            if self.room_propriety:
                _LOGGER.debug(f"Got {self.shared.file_name} Rooms Attributes.")
        return self.room_propriety

    async def async_get_robot_in_room(self, robot_y, robot_x, angle):
        """Get the robot position and return in what room is."""
        if self.robot_in_room:
            if (
                (self.robot_in_room["right"] >= int(robot_x))
                and (self.robot_in_room["left"] <= int(robot_x))
            ) and (
                (self.robot_in_room["down"] >= int(robot_y))
                and (self.robot_in_room["up"] <= int(robot_y))
            ):
                temp = {
                    "x": robot_x,
                    "y": robot_y,
                    "angle": angle,
                    "in_room": self.robot_in_room["room"],
                }
                return temp
        # else we need to search and use the async method.
        _LOGGER.debug(f"{self.shared.file_name} changed room.. searching..")
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
                (self.robot_in_room["right"] >= int(robot_x))
                and (self.robot_in_room["left"] <= int(robot_x))
            ) and (
                (self.robot_in_room["down"] >= int(robot_y))
                and (self.robot_in_room["up"] <= int(robot_y))
            ):
                temp = {
                    "x": robot_x,
                    "y": robot_y,
                    "angle": angle,
                    "in_room": self.robot_in_room["room"],
                }
                _LOGGER.debug(
                    f"{self.shared.file_name} is in {self.robot_in_room['room']}"
                )
                del room, corners, robot_x, robot_y  # free memory.
                return temp
        del room, corners  # free memory.
        _LOGGER.debug(f"{self.shared.file_name} not located in any Room")
        self.robot_in_room = None
        temp = {
            "x": robot_x,
            "y": robot_y,
            "angle": angle,
        }
        # If the robot is not inside any room, return None or a default value
        return temp

    def get_calibration_data(self, rotation_angle):
        """Get the calibration data from the JSON data.
        this will create the attribute calibration points."""
        calibration_data = []
        self.img_rotate = rotation_angle
        _LOGGER.info(f"Getting {self.shared.file_name} Calibrations points.")
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
            # self.shared.attr_calibration_points = calibration_data
        return calibration_data

    async def async_copy_array(self, original_array):
        """Copy the array."""
        _LOGGER.info(f"{self.shared.file_name}: Copying the array.")
        # copied_array = (this should save memory) np.copy(original_array)
        return np.copy(original_array)

    async def calculate_array_hash(self, layers: None, active: None):
        """Calculate the hash of the image based on the layers and active segments walls."""
        # todo: refactor this function to thread safe.
        _LOGGER.info(f"{self.shared.file_name}: Calculating the hash of the image.")
        if layers and active:
            data_to_hash = {
                "layers": len(layers["wall"][0]),
                "active_segments": tuple(active),
            }
            data_json = json.dumps(data_to_hash, sort_keys=True)
            hash_value = hashlib.sha256(data_json.encode()).hexdigest()
        else:
            hash_value = None
        return hash_value

    async def async_trim_and_resize_image(
        self, base_layer, color_background, margins, image_rotate
    ):
        """Trim and resize the image. This function is part of the SVG creation process."""
        swg_img_np = await self.async_auto_crop_and_trim_array(
            base_layer, color_background, margins, image_rotate
        )
        temp_png = Image.fromarray(swg_img_np, mode="RGBA")
        temp_png_resize = temp_png.resize((640, 480))
        result = np.array(temp_png_resize)
        return result

    async def async_draw_shapes(self, dwg, coordinates_data):
        """Draw the shapes on the SVG image."""
        # todo: refactor this function
        for color_data, coordinates_list in coordinates_data:
            # If there's only one point, draw a circle
            points_str = " ".join([f"{x},{y}" for x, y in coordinates_list])
            points = [tuple(map(int, point.split(","))) for point in points_str.split()]
            sorted_coordinates = sorted(points, key=lambda coord: coord[0])
            poly_points = self.simplify_polygon(sorted_coordinates)
            print(poly_points)
            if poly_points is []:
                continue
            if len(poly_points) == 1:
                print("is Point", color_data)
                x, y = poly_points[0]
                dwg.add(
                    dwg.circle(
                        center=(int(x), int(y)),
                        r=1,
                        fill=f"rgb({color_data[0]}, "
                        f"{color_data[1]}, {color_data[2]})",
                    )
                )
            else:
                # If there are multiple points, check if it's a closed shape
                is_closed = poly_points[0] == poly_points[-1]
                print(is_closed)
                # Use Polyline for open shapes, and Polygon for closed shapes
                if is_closed:
                    print("is Polygon:", color_data)
                    points = poly_points
                    dwg.add(
                        shapes.Polygon(
                            points=points,
                            fill=f"rgb({color_data[0]}, {color_data[1]},"
                            f" {color_data[2]})",
                        )
                    )
                else:
                    print("is Polyline", color_data)
                    dwg.add(
                        shapes.Polyline(
                            points=poly_points,
                            fill="none",
                            stroke=f"rgb({color_data[0]}, {color_data[1]}, {color_data[2]})",
                        )
                    )

    async def async_numpy_array_to_svg(
        self, base_layer, colours_list, color_background
    ):
        """Convert the numpy array to an SVG image."""
        # Create an SVG image 640 * 480
        dwg = svgwrite.Drawing(
            self.shared.svg_path, profile="tiny", size=("640px", "480px")
        )

        # Define a separate async function for trimming and resizing the image
        async def trim_and_resize_image_async():
            """Trim and resize the image warped."""
            return await self.async_trim_and_resize_image(
                base_layer,
                color_background,
                self.shared.margins,
                self.shared.image_rotate,
            )

        _LOGGER.debug("SVG from Numpy data start.")
        trimmed_and_resized_image = await trim_and_resize_image_async()
        coordinates_result = await self.data.async_extract_color_coordinates(
            trimmed_and_resized_image, colours_list
        )
        await self.async_draw_shapes(dwg, coordinates_result)
        dwg.save()

    @staticmethod
    def simplify_polygon(sorted_coordinates):
        """Simplify the polygon to avoid a huge SVG."""
        # todo: refactor this function

        simplified_coordinates = []

        i = 0
        while i < len(sorted_coordinates):
            start_point = sorted_coordinates[i]
            current_y = start_point[0]

            # Find the end of the run with the same y-coordinate
            while i < len(sorted_coordinates) and sorted_coordinates[i][0] == current_y:
                i += 1

            # Add the first and last points of the run to the simplified list
            simplified_coordinates.append(start_point)
            if i < len(sorted_coordinates):
                simplified_coordinates.append(sorted_coordinates[i - 1])

        # simplified_coordinates.append(simplified_coordinates[0])

        return simplified_coordinates

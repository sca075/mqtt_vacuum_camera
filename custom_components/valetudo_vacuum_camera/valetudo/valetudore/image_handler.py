"""
Image Handler Module dor Valetudo Re Vacuums.
It returns the PIL PNG image frame relative to the Map Data extrapolated from the vacuum json.
It also returns calibration, rooms data to the card and other images information to the camera.
Last Changed on Version: 1.5.2
"""
from __future__ import annotations

import logging
import uuid
import json
import numpy as np
from PIL import Image
from custom_components.valetudo_vacuum_camera.utils.colors_man import color_grey
from custom_components.valetudo_vacuum_camera.types import Color, Colors
from custom_components.valetudo_vacuum_camera.utils.img_data import ImageData
from custom_components.valetudo_vacuum_camera.utils.draweble import Drawable


_LOGGER = logging.getLogger(__name__)


# noinspection PyTypeChecker
class ReImageHandler(object):
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
                _LOGGER.debug(self.crop_area)
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

        _LOGGER.debug("Auto Crop and Trim Box data: %s", self.crop_area)
        self.crop_img_size = (rotated.shape[1], rotated.shape[0])
        _LOGGER.debug("Auto Crop and Trim image size: %s", self.crop_img_size)
        return rotated

    def extract_room_properties(self, json_data, destinations):
        unsorted_id = ImageData.get_rrm_segments_ids(json_data)
        size_x, size_y = ImageData.get_rrm_image_size(json_data)
        top, left = ImageData.get_rrm_image_position(json_data)
        dummy_segments, outlines = ImageData.get_rrm_segments(json_data,
                                                              size_x,
                                                              size_y,
                                                              top,
                                                              left,
                                                              True)
        del dummy_segments  # free memory
        dest_json = json.loads(destinations)
        room_data = dict(dest_json).get("rooms", [])
        zones_data = dict(dest_json).get("zones", [])
        points_data = dict(dest_json).get("spots", [])
        room_id_to_data = {room["id"]: room for room in room_data}
        self.rooms_pos = []
        room_properties = {}
        zone_properties = {}
        point_properties = {}
        for id_x, room_id in enumerate(unsorted_id):
            if room_id in room_id_to_data:
                room_info = room_id_to_data[room_id]
                name = room_info.get("name")
                # Calculate x and y min/max from outlines
                x_min = outlines[id_x][0][0]
                x_max = outlines[id_x][1][0]
                y_min = outlines[id_x][0][1]
                y_max = outlines[id_x][1][1]
                corners = [(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)]
                # rand256 vacuums accept int(room_id) or str(name)
                # the card will soon support int(room_id) but the camera will send name
                # this avoids the manual change of the values in the card.
                self.rooms_pos.append(
                    {
                        "name": name,
                        "corners": corners
                    }
                )
                room_properties[int(room_id)] = {
                    "number": int(room_id),
                    "outline": corners,
                    "name": name,
                    "x": (x_min + x_max) // 2,
                    "y": (y_min + y_max) // 2,
                }
        id_count = 1
        for zone in zones_data:
            zone_name = zone.get("name")
            coordinates = zone.get("coordinates")
            coordinates[0].pop()
            x1, y1, x2, y2 = coordinates[0]
            if coordinates:
                zone_properties[zone_name] = {
                    "zones": coordinates,
                    "name": zone_name,
                    "x": ((x1 + x2) // 2),
                    "y": ((y1 + y2) // 2),
                }
                id_count += 1
        id_count = 1
        for point in points_data:
            point_name = point.get("name")
            coordinates = point.get("coordinates")
            x1, y1 = coordinates
            if coordinates:
                point_properties[id_count] = {
                    "position": coordinates,
                    "name": point_name,
                    "x": x1,
                    "y": y1,
                }
                id_count += 1
        if room_properties != {}:
            if zone_properties != {}:
                _LOGGER.debug("Rooms and Zones, data extracted!")
            else:
                _LOGGER.debug("Rooms, data extracted!")
        elif zone_properties != {}:
            _LOGGER.debug("Zones, data extracted!")
        else:
            self.rooms_pos = None
            _LOGGER.debug("Rooms and Zones data not available!")
        return room_properties, zone_properties, point_properties

    async def get_image_from_rrm(
            self,
            m_json,
            robot_state,
            img_rotation: int = 0,
            margins: int = 150,
            user_colors: Colors = None,
            rooms_colors: Color = None,
            file_name: "" = None,
            destinations: None = None,
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
                _LOGGER.info(file_name + ":Composing the image for the camera.")
                # buffer json data
                self.json_data = m_json
                if self.room_propriety:
                    _LOGGER.info(file_name + ": Supporting Rooms Cleaning!")
                size_x, size_y = self.data.get_rrm_image_size(m_json)
                ##########################
                self.img_size = {
                    "x": 5120,
                    "y": 5120,
                    "centre": [(5120 // 2), (5120 // 2)],
                }
                ###########################
                self.json_id = str(uuid.uuid4())  # image id
                _LOGGER.info("Vacuum Data ID: %s", self.json_id)
                # grab data from the json data
                pos_top, pos_left = self.data.get_rrm_image_position(m_json)
                floor_data = self.data.get_rrm_floor(m_json)
                walls_data = self.data.get_rrm_walls(m_json)
                robot_pos = self.data.get_rrm_robot_position(m_json)
                go_to = self.data.get_rrm_goto_target(m_json)
                charger_pos = self.data.rrm_coordinates_to_valetudo(self.data.get_rrm_charger_position(m_json))
                zone_clean = self.data.get_rrm_currently_cleaned_zones(m_json)
                no_go_area = self.data.get_rrm_forbidden_zones(m_json)
                virtual_walls = self.data.get_rrm_virtual_walls(m_json)
                path_pixel = self.data.get_rrm_path(m_json)
                path_pixel2 = self.data.sublist_join(
                    self.data.rrm_valetudo_path_array(path_pixel["points"]), 2)
                robot_position = None
                robot_position_angle = None
                # convert the data to reuse the current drawing library
                robot_pos = self.data.rrm_coordinates_to_valetudo(robot_pos)
                if robot_pos:
                    robot_position = robot_pos
                    angle = self.data.get_rrm_robot_angle(m_json)
                    robot_position_angle = round(angle[0], 0)
                    _LOGGER.debug(f"robot position: {robot_pos}, robot angle: {robot_position_angle}")
                    if self.rooms_pos is None:
                        self.robot_pos = {
                            "x": robot_position[0] * 10,
                            "y": robot_position[1] * 10,
                            "angle": robot_position_angle,
                        }
                    else:
                        self.robot_pos = await self.get_robot_in_room(
                            (robot_position[0] * 10),
                            (robot_position[1] * 10),
                            robot_position_angle)
                _LOGGER.debug("charger position: %s", charger_pos)
                if charger_pos:
                    self.charger_pos = {
                        "x": charger_pos[0],
                        "y": charger_pos[1],
                    }

                pixel_size = 5
                _LOGGER.info(file_name + ": Empty image with background color")
                img_np_array = await self.draw.create_empty_image(5120, 5120, color_background)
                _LOGGER.info(file_name + ": Overlapping Layers")
                # this below are floor data
                pixels = self.data.from_rrm_to_compressed_pixels(floor_data,
                                                                 image_width=size_x,
                                                                 image_height=size_y,
                                                                 image_top=pos_top,
                                                                 image_left=pos_left)
                # checking if there are segments too (sorted pixels in the raw data).
                segments = self.data.get_rrm_segments(m_json, size_x, size_y, pos_top, pos_left)
                room_id = 0
                if (segments and pixels) or pixels:
                    room_color = rooms_colors[room_id]
                    # drawing floor
                    if pixels:
                        img_np_array = await self.draw.from_json_to_image(
                            img_np_array, pixels, pixel_size, room_color
                        )
                    # drawing segments floor
                    if segments:
                        for pixels in segments:
                            room_id += 1
                            if room_id > 15:
                                room_id = 0
                            room_color = rooms_colors[room_id]
                            img_np_array = await self.draw.from_json_to_image(
                                img_np_array, pixels, pixel_size, room_color
                            )

                _LOGGER.info(file_name + ": Completed floor Layers")
                # Drawing walls.
                walls = self.data.from_rrm_to_compressed_pixels(walls_data,
                                                                image_width=size_x,
                                                                image_height=size_y,
                                                                image_left=pos_left,
                                                                image_top=pos_top)
                if walls:
                    img_np_array = await self.draw.from_json_to_image(
                        img_np_array, walls, pixel_size, color_wall
                    )
                    _LOGGER.info(file_name + ": Completed base Layers")

                if (room_id > 0) and not self.room_propriety:
                    _LOGGER.debug("we have rooms..")
                    self.room_propriety = await self.get_rooms_attributes(destinations)
                    self.robot_pos = await self.get_robot_in_room(
                        (robot_position[0] * 10),
                        (robot_position[1] * 10),
                        robot_position_angle)
                # charger
                if charger_pos:
                    img_np_array = await self.draw.battery_charger(
                        img_np_array, charger_pos[0], charger_pos[1], color_charger
                    )
                # If there is a zone clean we draw it now.
                self.frame_number += 1
                _LOGGER.debug(file_name + ": Frame number %s", self.frame_number)
                if self.frame_number > 5:
                    self.frame_number = 0
                # zone clean
                if zone_clean:
                    img_np_array = await self.draw.zones(
                        img_np_array,
                        zone_clean,
                        color_zone_clean
                    )
                # no-go zones
                if no_go_area:
                    img_np_array = await self.draw.zones(
                        img_np_array,
                        no_go_area,
                        color_no_go
                    )
                # virtual walls
                if virtual_walls:
                    img_np_array = await self.draw.draw_virtual_walls(
                        img_np_array, virtual_walls, color_no_go
                    )
                # draw path
                if path_pixel2:
                    img_np_array = await self.draw.lines(
                        img_np_array, path_pixel2, 5, color_move
                    )
                # go to flag and predicted path
                if go_to:
                    img_np_array = await self.draw.go_to_flag(
                        img_np_array,
                        (go_to[0], go_to[1]),
                        self.img_rotate,
                        color_go_to,
                    )
                    predicted_path = self.data.get_rrm_goto_predicted_path(m_json)
                    if predicted_path:
                        img_np_array = await self.draw.lines(
                            img_np_array,
                            predicted_path,
                            3,
                            color_grey
                        )
                # rotate the robot if docked
                if robot_state == "docked":
                    robot_position_angle = robot_position_angle - 180  # rotation offset
                # draw the robot
                if robot_position and robot_position_angle:
                    img_np_array = await self.draw.robot(
                        img_np_array,
                        robot_position[0],
                        robot_position[1],
                        robot_position_angle,
                        color_robot,
                        file_name,
                    )
                _LOGGER.debug(file_name + " Auto cropping the image with rotation: %s", int(img_rotation))
                img_np_array = await self.auto_crop_and_trim_array(
                    img_np_array,
                    color_background,
                    int(margins),
                    int(img_rotation),
                )
                pil_img = Image.fromarray(img_np_array, mode="RGBA")
                del img_np_array  # unload memory
                return pil_img

        except Exception as e:
            _LOGGER.warning(file_name + ": Error in get_image_from_json: %s", str(e))
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

    async def get_rooms_attributes(self, destinations: None):
        if self.room_propriety:
            return self.room_propriety
        if self.json_data and destinations:
            _LOGGER.debug("Checking for rooms data..")
            self.room_propriety = self.extract_room_properties(self.json_data, destinations)
            if self.room_propriety:
                _LOGGER.debug("Got Rooms Attributes.")
        return self.room_propriety

    async def get_robot_in_room(self, robot_x, robot_y, angle):
        # do we know where we are?
        if self.robot_in_room:
            if (
                    ((self.robot_in_room["left"] >= robot_x) and (self.robot_in_room["right"] <= robot_x))
                    and ((self.robot_in_room["up"] >= robot_y) and (self.robot_in_room["down"] <= robot_y))
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
                "left": corners[0][0],
                "right": corners[2][0],
                "up": corners[0][1],
                "down": corners[2][1],
                "room": room["name"],
            }
            # Check if the robot coordinates are inside the room's corners
            if (
                    ((self.robot_in_room["left"] >= robot_x) and (self.robot_in_room["right"] <= robot_x))
                    and ((self.robot_in_room["up"] >= robot_y) and (self.robot_in_room["down"] <= robot_y))
            ):
                temp = {
                    "x": robot_x,
                    "y": robot_y,
                    "angle": angle,
                    "in_room": self.robot_in_room["room"],
                }
                _LOGGER.debug("Robot is inside %s", self.robot_in_room['room'])
                del room, corners, robot_x, robot_y  # free memory.
                return temp
        del room, corners, robot_x, robot_y  # free memory.
        _LOGGER.debug("Robot is not inside any room")
        self.robot_in_room = None
        # If the robot is not inside any room, return None or a default value
        return self.robot_in_room

    def get_calibration_data(self, rotation_angle):
        if not self.calibration_data:
            self.calibration_data = []
            self.img_rotate = rotation_angle
            _LOGGER.info("Getting Calibrations points %s", self.crop_area)
            # Calculate the calibration points in the vacuum coordinate system
            # Valetudo Re version need corrections of the coordinates and are implemented with *10

            vacuum_points = [
                {"x": (self.crop_area[0]*10), "y": (self.crop_area[1]*10)},  # Top-left corner 0
                {"x": (self.crop_area[2]*10), "y": (self.crop_area[1]*10)},  # Top-right corner 1
                {"x": (self.crop_area[2]*10), "y": (self.crop_area[3]*10)},  # Bottom-right corner 2
                {
                    "x": (self.crop_area[0]*10),
                    "y": (self.crop_area[3]*10),
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
                self.calibration_data.append(calibration_point)

            return self.calibration_data
        else:
            return self.calibration_data

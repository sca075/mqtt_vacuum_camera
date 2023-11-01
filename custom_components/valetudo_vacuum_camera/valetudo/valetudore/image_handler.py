"""
Image Handler Module dor Valetudo Re Vacuums.
It returns the PIL PNG image frame relative to the Map Data extrapolated from the vacuum json.
It also returns calibration, rooms data to the card and other images information to the camera.
Last Changed on Version: 1.4.8
"""
from __future__ import annotations

import logging
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
        self.img_size = None
        self.crop_area = None
        self.crop_img_size = None
        self.img_base_layer = None
        self.frame_number = 0
        self.path_pixels = None
        self.robot_pos = None
        self.charger_pos = None
        self.json_id = None
        self.json_data = None
        self.go_to = None
        self.img_rotate = 0
        self.room_propriety = None
        self.data = ImageData
        self.draw = Drawable

    async def crop_and_trim_array(
            self,
            image_array,
            crop_percentage,
            trim_u=0,
            trim_b=0,
            trim_l=0,
            trim_r=0,
            rotate: int = 0,
    ):
        """Crops and trims a numpy array and returns the processed image and scale factor."""
        center_x = image_array.shape[1] // 2
        center_y = image_array.shape[0] // 2

        if crop_percentage > 10:
            # Calculate the crop size based on crop_percentage
            crop_size = int(min(center_x, center_y) * crop_percentage / 100)

            # Calculate the initial crop box at 0 degrees rotation
            cropbox = (
                center_x - crop_size,
                center_y - crop_size,
                center_x + crop_size,
                center_y + crop_size,
            )

            # Crop the image based on the initial crop box
            cropped = image_array[cropbox[1]:cropbox[3], cropbox[0]:cropbox[2]]

            # Rotate the cropped image based on the given angle
            if rotate == 90:
                rotated = np.rot90(cropped, 1)
            elif rotate == 180:
                rotated = np.rot90(cropped, 2)
            elif rotate == 270:
                rotated = np.rot90(cropped, 3)
            else:
                rotated = cropped

            if crop_percentage == 100:
                _LOGGER.warning(
                    "Returning Vacuum Map at 100%! This can affect HA performance!!"
                )
                self.crop_area = cropbox
                self.crop_img_size = (cropped.shape[1], cropped.shape[0])
                return cropped

            # Calculate the dimensions after trimming
            trimmed_width = cropbox[2] - cropbox[0] - trim_l - trim_r
            trimmed_height = cropbox[3] - cropbox[1] - trim_u - trim_b

            if trimmed_width <= 99 or trimmed_height <= 99:
                _LOGGER.warning(
                    "Invalid trim values result in an improperly sized image, returning un-trimmed image!"
                )
                self.crop_area = cropbox
                self.crop_img_size = (cropped.shape[1], cropped.shape[0])
                return cropped
            else:
                # Apply the trim values to the rotated image
                trimmed = rotated[
                          trim_u:rotated.shape[0] - trim_b,
                          trim_l:rotated.shape[1] - trim_r,
                          ]
                # Calculate the crop area in the original image_array
                if rotate == 90:
                    new_cropbox = (
                        cropbox[0] + trim_b,
                        cropbox[1] + trim_l,
                        cropbox[2] - trim_u,
                        cropbox[3] - trim_r,
                    )
                elif rotate == 180:
                    new_cropbox = (
                        cropbox[0] + trim_r,
                        cropbox[1] + trim_b,
                        cropbox[2] - trim_l,
                        cropbox[3] - trim_u,
                    )
                elif rotate == 270:
                    new_cropbox = (
                        cropbox[0] + trim_u,
                        cropbox[1] + trim_r,
                        cropbox[2] - trim_b,
                        cropbox[3] - trim_l,
                    )
                else:
                    new_cropbox = (
                        cropbox[0] + trim_l,
                        cropbox[1] + trim_u,
                        cropbox[2] - trim_r,
                        cropbox[3] - trim_b,
                    )

                self.crop_area = new_cropbox
                _LOGGER.debug("Crop and Trim Box data: %s", self.crop_area)
                self.crop_img_size = (trimmed.shape[1], trimmed.shape[0])
                _LOGGER.debug("Crop and Trim image size: %s", self.crop_img_size)
                return trimmed
        else:
            _LOGGER.warning("Cropping value is below 10%. Returning un-cropped image!")
            self.crop_img_size = (image_array.shape[1], image_array.shape[0])
            return image_array

    @staticmethod
    def extract_room_properties(json_data):
        room_properties = {}
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
                    room_name = str(segment_id)
                    room_properties[room_name] = {
                        "number": segment_id,
                        "outline": corners,
                        "name": name,
                        "x": ((x_min + x_max) // 2),
                        "y": ((y_min + y_max) // 2),
                    }
        _LOGGER.debug("Rooms data extracted!")
        return room_properties

    async def get_image_from_rrm(
            self,
            m_json,
            robot_state,
            img_rotation: int = 0,
            crop: int = 50,
            trim_u: int = 0,
            trim_b: int = 0,
            trim_l: int = 0,
            trim_r: int = 0,
            user_colors: Colors = None,
            rooms_colors: Color = None,
            file_name: "" = None,
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
                _LOGGER.debug("image size %s", [size_x, size_y])
                ##########################
                self.img_size = {
                    "x": 5120,
                    "y": 5120,
                    "centre": [(5120 // 2), (5120 // 2)],
                }
                ###########################
                self.json_id = "Not Generated"
                _LOGGER.info("Vacuum JSon ID: %s", self.json_id)
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
                robot_pos = self.data.rrm_coordinates_to_valetudo(robot_pos)
                if robot_pos:
                    robot_position = robot_pos
                    angle = self.data.get_rrm_robot_angle(m_json)
                    if angle[0] == 0:
                        robot_position_angle = self.data.convert_negative_angle(
                            path_pixel['current_angle']
                        )
                        # ((int(path_pixel['current_angle']) + 450) % 360)
                    else:
                        robot_position_angle = angle[0]
                        # ((int(angle[1]) + 450) % 360)
                    _LOGGER.debug("robot position: %s", robot_pos)
                    _LOGGER.debug("robot angle: %s", robot_position_angle)
                    self.robot_pos = {
                        "x": robot_position[0],
                        "y": robot_position[1],
                        "angle": robot_position_angle,
                    }
                _LOGGER.debug("charger position: %s", charger_pos)
                if charger_pos:
                    self.charger_pos = {
                        "x": charger_pos[0],
                        "y": charger_pos[1],
                    }

                pixel_size = 5
                # layers = self.data.find_layers(m_json["layers"]
                # _LOGGER.debug(file_name + ": Layers to draw: %s", layers.keys())
                _LOGGER.info(file_name + ": Empty image with background color")
                img_np_array = await self.draw.create_empty_image(5120, 5120, color_background)
                _LOGGER.info(file_name + ": Overlapping Layers")
                pixels = self.data.from_rrm_to_compressed_pixels(floor_data,
                                                                 image_width=size_x,
                                                                 image_height=size_y,
                                                                 image_top=pos_top,
                                                                 image_left=pos_left)
                segments = self.data.get_rrm_segments(m_json, size_x, size_y, pos_top, pos_left)
                if (segments and pixels) or pixels:
                    room_id = 0
                    room_color = rooms_colors[room_id]
                    if pixels:
                        img_np_array = await self.draw.from_json_to_image(
                            img_np_array, pixels, pixel_size, room_color
                        )
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
                if charger_pos:
                    img_np_array = await self.draw.battery_charger(
                        img_np_array, charger_pos[0], charger_pos[1], color_charger
                    )
                # self.img_base_layer = img_np_array
                self.frame_number += 1
                # If there is a zone clean we draw it now.
                _LOGGER.debug(file_name + ": Frame number %s", self.frame_number)
                self.frame_number += 1
                if self.frame_number > 5:
                    self.frame_number = 0
                # zone clean
                if zone_clean:
                    img_np_array = await self.draw.zones(
                        img_np_array,
                        zone_clean,
                        color_zone_clean
                    )
                if no_go_area:
                    img_np_array = await self.draw.zones(
                        img_np_array,
                        no_go_area,
                        color_no_go
                    )
                if virtual_walls:
                    img_np_array = await self.draw.draw_virtual_walls(
                        img_np_array, virtual_walls, color_no_go
                    )
                # draw path
                if path_pixel2:
                    img_np_array = await self.draw.lines(
                        img_np_array, path_pixel2, 5, color_move
                    )

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

                if robot_state == "docked":
                    robot_position_angle = robot_position_angle - 180  # rotation offset
                if robot_position and robot_position_angle:
                    img_np_array = await self.draw.robot(
                        img_np_array,
                        robot_position[0],
                        robot_position[1],
                        robot_position_angle,
                        color_robot,
                        file_name,
                    )
                _LOGGER.debug(file_name + " Image Cropping:" + str(crop) + " Image Rotate:" + str(img_rotation))
                img_np_array = await self.crop_and_trim_array(
                    img_np_array,
                    crop,
                    int(trim_u),
                    int(trim_b),
                    int(trim_l),
                    int(trim_r),
                    int(img_rotation),
                )
                pil_img = Image.fromarray(img_np_array, mode="RGBA")
                del img_np_array
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

    async def get_rooms_attributes(self):
        if self.json_data:
            _LOGGER.debug("Checking for rooms data..")
            self.room_propriety = ReImageHandler.extract_room_properties(self.json_data)
            if self.room_propriety:
                _LOGGER.debug("Got Rooms Attributes.")
        return self.room_propriety

    def get_calibration_data(self, rotation_angle):
        calibration_data = []
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
            calibration_data.append(calibration_point)

        return calibration_data

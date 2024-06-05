"""
Image Handler Class.
It returns the PIL PNG image frame relative to the Map Data extrapolated from the vacuum json.
It also returns calibration, rooms data to the card and other images information to the camera.
Version: 2024.06.2
"""

from __future__ import annotations

import json
import logging

from PIL import Image, ImageOps
import numpy as np

from custom_components.valetudo_vacuum_camera.types import (
    CalibrationPoints,
    ChargerPosition,
    Color,
    ImageSize,
    NumpyArray,
    RobotPosition,
    RoomsProperties,
)
from custom_components.valetudo_vacuum_camera.utils.colors_man import color_grey
from custom_components.valetudo_vacuum_camera.utils.drawable import Drawable
from custom_components.valetudo_vacuum_camera.utils.img_data import ImageData
from custom_components.valetudo_vacuum_camera.valetudo.hypfer.handler_utils import (
    ImageUtils as ImUtils,
)
from custom_components.valetudo_vacuum_camera.valetudo.hypfer.image_draw import (
    ImageDraw as ImDraw,
)

_LOGGER = logging.getLogger(__name__)


class MapImageHandler(object):
    """Map Image Handler Class.
    This class is used to handle the image data and the drawing of the map."""

    def __init__(self, shared_data):
        """Initialize the Map Image Handler."""
        self.auto_crop = None  # auto crop data to be calculate once.
        self.calibration_data = None  # camera shared data.
        self.charger_pos = None  # vacuum data charger position.
        self.crop_area = None  # module shared for calibration data.
        self.crop_img_size = None  # size of the image cropped calibration data.
        self.data = ImageData  # imported Image Data Module.
        self.draw = Drawable  # imported Drawing utilities
        self.go_to = None  # vacuum go to data
        self.file_name = shared_data.file_name  # file name of the vacuum.
        self.img_hash = None  # hash of the image calculated to check differences.
        self.img_base_layer = None  # numpy array store the map base layer.
        self.img_size = None  # size of the created image
        self.json_data = None  # local stored and shared json data.
        self.json_id = None  # grabbed data of the vacuum image id.
        self.path_pixels = None  # vacuum path datas.
        self.robot_in_room = None  # vacuum room position.
        self.robot_pos = None  # vacuum coordinates.
        self.room_propriety = None  # vacuum segments data.
        self.rooms_pos = None  # vacuum room coordinates / name list.
        self.active_zones = None  # vacuum active zones.
        self.frame_number = 0  # frame number of the image.
        self.zooming = False  # zooming the image.
        self.shared = shared_data  # camera shared data
        self.svg_wait = False  # SVG image creation wait.
        self.trim_down = None  # memory stored trims calculated once.
        self.trim_left = None  # memory stored trims calculated once.
        self.trim_right = None  # memory stored trims calculated once.
        self.trim_up = None  # memory stored trims calculated once.
        self.offset_top = self.shared.offset_top  # offset top
        self.offset_bottom = self.shared.offset_down  # offset bottom
        self.offset_left = self.shared.offset_left  # offset left
        self.offset_right = self.shared.offset_right  # offset right
        self.offset_x = 0  # offset x for the aspect ratio.
        self.offset_y = 0  # offset y for the aspect ratio.
        self.imd = ImDraw(self)
        self.imu = ImUtils(self)

    async def async_auto_trim_and_zoom_image(
        self,
        image_array: NumpyArray,
        detect_colour: Color = color_grey,
        margin_size: int = 0,
        rotate: int = 0,
        zoom: bool = False,
    ):
        """
        Automatically crops and trims a numpy array and returns the processed image.
        """
        try:
            if not self.auto_crop:
                # Find the coordinates of the first occurrence of a non-background color
                nonzero_coords = np.column_stack(
                    np.where(image_array != list(detect_colour))
                )
                # Calculate the trim box based on the first and last occurrences
                min_y, min_x, _ = np.min(nonzero_coords, axis=0)
                max_y, max_x, _ = np.max(nonzero_coords, axis=0)
                del nonzero_coords
                _LOGGER.debug(
                    "{}: Found trims max and min values (y,x) ({}, {}) ({},{})...".format(
                        self.file_name,
                        int(max_y),
                        int(max_x),
                        int(min_y),
                        int(min_x),
                    )
                )
                # Calculate and store the trims coordinates with margins
                self.trim_left = int(min_x) + self.offset_left - margin_size
                self.trim_up = int(min_y) + self.offset_top - margin_size
                self.trim_right = int(max_x) - self.offset_right + margin_size
                self.trim_down = int(max_y) - self.offset_bottom + margin_size
                del min_y, min_x, max_x, max_y

                # Calculate the dimensions after trimming using min/max values
                trimmed_width = max(0, self.trim_right - self.trim_left)
                trimmed_height = max(0, self.trim_down - self.trim_up)
                self.shared.image_ref_height = trimmed_height
                self.shared.image_ref_width = trimmed_width

                # Test if the trims are okay or not
                if trimmed_height <= margin_size or trimmed_width <= margin_size:
                    _LOGGER.debug(
                        f"{self.file_name}: Background colour not detected at rotation {rotate}."
                    )
                    pos_0 = 0
                    self.crop_area = [
                        pos_0,
                        pos_0,
                        image_array.shape[1],
                        image_array.shape[0],
                    ]
                    self.img_size = (image_array.shape[1], image_array.shape[0])
                    del trimmed_width, trimmed_height
                    return image_array

                # Store Crop area of the original image_array we will use from the next frame.
                self.auto_crop = [
                    self.trim_left,
                    self.trim_up,
                    self.trim_right,
                    self.trim_down,
                ]
            # If it is needed to zoom the image.
            trimmed = await self.imu.async_check_if_zoom_is_on(
                image_array, margin_size, zoom
            )
            del image_array  # Free memory.
            # Rotate the cropped image based on the given angle
            rotated = await self.imu.async_rotate_the_image(trimmed, rotate)
            del trimmed  # Free memory.
            _LOGGER.debug(f"{self.file_name}: Auto Trim Box data: {self.crop_area}")
            self.crop_img_size = [rotated.shape[1], rotated.shape[0]]
            _LOGGER.debug(
                f"{self.file_name}: Auto Trimmed image size: {self.crop_img_size}"
            )

        except Exception as e:
            _LOGGER.warning(
                f"{self.file_name}: Error {e} during auto trim and zoom.",
                exc_info=True,
            )
            return None
        return rotated

    async def async_extract_room_properties(self, json_data):
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
                    compressed_pixels = layer.get("compressedPixels", [])
                    pixels = self.data.sublist(compressed_pixels, 3)
                    # Calculate x and y min/max from compressed pixels
                    x_min, y_min, x_max, y_max = await self.data.get_rooms_coordinates(
                        pixels, pixel_size
                    )
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
            _LOGGER.debug(f"{self.file_name}: Rooms data extracted!")
        else:
            _LOGGER.debug(f"{self.file_name}: Rooms data not available!")
            self.rooms_pos = None
        return room_properties

    # noinspection PyUnresolvedReferences,PyUnboundLocalVariable
    async def async_get_image_from_json(
        self,
        m_json: json | None,
    ) -> Image.Image | None:
        """Get the image from the JSON data.
        It uses the ImageDraw class to draw some of the elements of the image.
        The robot itself will be drawn in this function as per some of the values are needed for other tasks.
        @param m_json: The JSON data to use to draw the image.
        @return Image.Image: The image to display.
        """
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
                # buffer json data
                self.json_data = m_json
                # Get the image size from the JSON data
                size_x = int(m_json["size"]["x"])
                size_y = int(m_json["size"]["y"])
                self.img_size = {
                    "x": size_x,
                    "y": size_y,
                    "centre": [(size_x // 2), (size_y // 2)],
                }
                # Get the JSON ID from the JSON data.
                self.json_id = await self.imd.async_get_json_id(m_json)
                # Check entity data.
                entity_dict = await self.imd.async_get_entity_data(m_json)
                # Update the Robot position.
                robot_pos, robot_position, robot_position_angle = (
                    await self.imd.async_get_robot_position(entity_dict)
                )

                # Get the pixels size and layers from the JSON data
                pixel_size = int(m_json["pixelSize"])
                layers, active = self.data.find_layers(m_json["layers"])
                new_frame_hash = await self.imd.calculate_array_hash(layers, active)
                if self.frame_number == 0:
                    self.img_hash = new_frame_hash
                    # empty image
                    img_np_array = await self.draw.create_empty_image(
                        size_x, size_y, color_background
                    )
                    # overlapping layers
                    for layer_type, compressed_pixels_list in layers.items():
                        room_id, img_np_array = await self.imd.async_draw_base_layer(
                            img_np_array,
                            compressed_pixels_list,
                            layer_type,
                            color_wall,
                            color_zone_clean,
                            pixel_size,
                        )
                    # Draw the virtual walls if any.
                    img_np_array = await self.imd.async_draw_virtual_walls(
                        m_json, img_np_array, color_no_go
                    )
                    # Draw charger.
                    img_np_array = await self.imd.async_draw_charger(
                        img_np_array, entity_dict, color_charger
                    )
                    # Draw obstacles if any.
                    img_np_array = await self.imd.async_draw_obstacle(
                        img_np_array, entity_dict, color_no_go
                    )
                    # Robot and rooms position
                    if (room_id > 0) and not self.room_propriety:
                        self.room_propriety = await self.async_extract_room_properties(
                            self.json_data
                        )
                        if self.rooms_pos and robot_position and robot_position_angle:
                            self.robot_pos = await self.imd.async_get_robot_in_room(
                                robot_x=(robot_position[0]),
                                robot_y=(robot_position[1]),
                                angle=robot_position_angle,
                            )
                    _LOGGER.info(f"{self.file_name}: Completed base Layers")
                    # Copy the new array in base layer.
                    self.img_base_layer = await self.imd.async_copy_array(img_np_array)
                self.shared.frame_number = self.frame_number
                self.frame_number += 1
                if (self.frame_number > 1024) or (new_frame_hash != self.img_hash):
                    self.frame_number = 0
                _LOGGER.debug(
                    f"{self.file_name}: {self.json_id} at Frame Number: {self.frame_number}"
                )
                # Copy the base layer to the new image.
                img_np_array = await self.imd.async_copy_array(self.img_base_layer)
                # All below will be drawn at each frame.
                # Draw zones if any.
                img_np_array = await self.imd.async_draw_zones(
                    m_json, img_np_array, color_zone_clean, color_no_go
                )
                # Draw the go_to target flag.
                img_np_array = await self.imd.draw_go_to_flag(
                    img_np_array, entity_dict, color_go_to
                )
                # Draw path prediction and paths.
                img_np_array = await self.imd.async_draw_paths(
                    img_np_array, m_json, color_move, color_grey
                )
                # Check if the robot is docked.
                if self.shared.vacuum_state == "docked":
                    # Adjust the robot angle.
                    robot_position_angle -= 180
                if robot_pos:
                    # Draw the robot
                    img_np_array = await self.draw.robot(
                        layers=img_np_array,
                        x=robot_position[0],
                        y=robot_position[1],
                        angle=robot_position_angle,
                        fill=color_robot,
                        log=self.file_name,
                    )
                # Resize the image
                img_np_array = await self.async_auto_trim_and_zoom_image(
                    img_np_array,
                    color_background,
                    int(self.shared.margins),
                    int(self.shared.image_rotate),
                    self.zooming,
                )
            # If the image is None return None and log the error.
            if img_np_array is None:
                _LOGGER.warning(f"{self.file_name}: Image array is None.")
                return None
            else:
                # Convert the numpy array to a PIL image
                pil_img = Image.fromarray(img_np_array, mode="RGBA")
                del img_np_array
            # reduce the image size if the zoomed image is bigger then the original.
            if (
                self.shared.image_auto_zoom
                and self.shared.vacuum_state == "cleaning"
                and self.zooming
                and self.shared.image_zoom_lock_ratio
                or self.shared.image_aspect_ratio != "None"
            ):
                width = self.shared.image_ref_width
                height = self.shared.image_ref_height
                if self.shared.image_aspect_ratio != "None":
                    wsf, hsf = [
                        int(x) for x in self.shared.image_aspect_ratio.split(",")
                    ]
                    new_aspect_ratio = wsf / hsf
                    aspect_ratio = width / height
                    if aspect_ratio > new_aspect_ratio:
                        new_width = int(pil_img.height * new_aspect_ratio)
                        new_height = pil_img.height
                    else:
                        new_width = pil_img.width
                        new_height = int(pil_img.width / new_aspect_ratio)
                    resized = ImageOps.pad(pil_img, (new_width, new_height))
                    self.crop_img_size[0], self.crop_img_size[1] = (
                        await self.async_map_coordinates_offset(
                            wsf, hsf, new_width, new_height
                        )
                    )
                    _LOGGER.debug(
                        f"{self.file_name}: Image Aspect Ratio ({wsf}, {hsf}): {new_width}x{new_height}"
                    )
                    _LOGGER.debug(f"{self.file_name}: Frame Completed.")
                    return resized
                else:
                    _LOGGER.debug(f"{self.file_name}: Frame Completed.")
                    return ImageOps.pad(pil_img, (width, height))
            else:
                _LOGGER.debug(f"{self.file_name}: Frame Completed.")
                return pil_img
        except RuntimeError or RuntimeWarning as e:
            _LOGGER.warning(
                f"{self.file_name}: Error {e} during image creation.",
                exc_info=True,
            )
            return None

    def get_frame_number(self) -> int:
        """Return the frame number of the image."""
        return self.frame_number

    def get_robot_position(self) -> RobotPosition | None:
        """Return the robot position."""
        return self.robot_pos

    def get_charger_position(self) -> ChargerPosition | None:
        """Return the charger position."""
        return self.charger_pos

    def get_img_size(self) -> ImageSize | None:
        """Return the size of the image."""
        return self.img_size

    def get_json_id(self) -> str | None:
        """Return the JSON ID from the image."""
        return self.json_id

    async def async_get_rooms_attributes(self) -> RoomsProperties:
        """Get the rooms attributes from the JSON data.
        :return: The rooms attribute's."""
        if self.room_propriety:
            return self.room_propriety
        if self.json_data:
            _LOGGER.debug(f"\nChecking {self.file_name} Rooms data..")
            self.room_propriety = await self.async_extract_room_properties(
                self.json_data
            )
            if self.room_propriety:
                _LOGGER.debug(f"\nGot {self.file_name} Rooms Attributes.")
        return self.room_propriety

    def get_calibration_data(self) -> CalibrationPoints:
        """Get the calibration data from the JSON data.
        this will create the attribute calibration points."""
        calibration_data = []
        rotation_angle = self.shared.image_rotate
        _LOGGER.info(f"\nGetting {self.file_name} Calibrations points.")

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
        # Calculate the calibration points in the vacuum coordinate system
        vacuum_points = self.imu.get_vacuum_points(rotation_angle)

        # Create the calibration data for each point
        for vacuum_point, map_point in zip(vacuum_points, map_points):
            calibration_point = {"vacuum": vacuum_point, "map": map_point}
            calibration_data.append(calibration_point)
        del vacuum_points, map_points, calibration_point, rotation_angle  # free memory.
        return calibration_data

    async def async_map_coordinates_offset(
        self, wsf: int, hsf: int, width: int, height: int
    ) -> tuple[int, int]:
        """
        Offset the coordinates to the map.
        :param wsf: Width scale factor.
        :param hsf: Height scale factor.
        :param width: Width of the image.
        :param height: Height of the image.
        """

        if wsf == 1 and hsf == 1:
            self.imu.set_image_offset_ratio_1_1(width, height)
            return width, height
        elif wsf == 2 and hsf == 1:
            self.imu.set_image_offset_ratio_2_1(width, height)
            return width, height
        elif wsf == 3 and hsf == 2:
            self.imu.set_image_offset_ratio_3_2(width, height)
            return width, height
        elif wsf == 5 and hsf == 4:
            self.imu.set_image_offset_ratio_5_4(width, height)
            return width, height
        elif wsf == 9 and hsf == 16:
            self.imu.set_image_offset_ratio_9_16(width, height)
            return width, height
        elif wsf == 16 and hsf == 9:
            self.imu.set_image_offset_ratio_16_9(width, height)
            return width, height
        else:
            return width, height

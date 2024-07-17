"""
Image Utils Class for Valetudo Hypfer Image Handling.
This class is used to simplify the ImageHandler class.
Version: 2024.07.2
"""

from __future__ import annotations

import logging

import numpy as np
from numpy import rot90

from custom_components.mqtt_vacuum_camera.types import Color, NumpyArray

_LOGGER = logging.getLogger(__name__)


class TrimError(Exception):
    """Exception raised for errors in the trim process."""

    def __init__(self, message, image):
        super().__init__(message)
        self.image = image


class ImageUtils:
    """Image Utils Class for Valetudo Hypfer Image Handler."""

    """It is used to simplify the ImageHandler class."""

    def __init__(self, image_handler):
        self.img = image_handler
        self.file_name = self.img.shared.file_name

    async def async_check_if_zoom_is_on(
        self, image_array: NumpyArray, margin_size: int = 100, zoom: bool = False
    ) -> NumpyArray:
        """Check if the image need to be zoom."""
        """async_auto_trim_and_zoom_image"""

        if (
            zoom
            and self.img.shared.vacuum_state == "cleaning"
            and self.img.shared.image_auto_zoom
        ):
            # Zoom the image based on the robot's position.
            _LOGGER.debug(
                f"{self.file_name}: Zooming the image on room {self.img.robot_in_room['room']}."
            )
            trim_left = self.img.robot_in_room["left"] - margin_size
            trim_right = self.img.robot_in_room["right"] + margin_size
            trim_up = self.img.robot_in_room["up"] - margin_size
            trim_down = self.img.robot_in_room["down"] + margin_size
            trimmed = image_array[trim_up:trim_down, trim_left:trim_right]
        else:
            # Apply the auto-calculated trims to the rotated image
            trimmed = image_array[
                self.img.auto_crop[1] : self.img.auto_crop[3],
                self.img.auto_crop[0] : self.img.auto_crop[2],
            ]
        return trimmed

    async def async_image_margins(
        self, image_array: NumpyArray, detect_colour: Color
    ) -> tuple[int, int, int, int]:
        """Crop the image based on the auto crop area."""
        """async_auto_trim_and_zoom_image"""

        nonzero_coords = np.column_stack(np.where(image_array != list(detect_colour)))
        # Calculate the trim box based on the first and last occurrences
        min_y, min_x, _ = NumpyArray.min(nonzero_coords, axis=0)
        max_y, max_x, _ = NumpyArray.max(nonzero_coords, axis=0)
        del nonzero_coords
        _LOGGER.debug(
            f"{self.file_name}: Found trims max and min values (y,x) "
            f"({int(max_y)}, {int(max_x)}) ({int(min_y)},{int(min_x)})..."
        )

        return min_y, min_x, max_x, max_y

    async def async_rotate_the_image(
        self, trimmed: NumpyArray, rotate: int
    ) -> NumpyArray:
        """Rotate the image and return the new array."""
        """async_auto_trim_and_zoom_image"""
        if rotate == 90:
            rotated = rot90(trimmed)
            self.img.crop_area = [
                self.img.trim_left,
                self.img.trim_up,
                self.img.trim_right,
                self.img.trim_down,
            ]
        elif rotate == 180:
            rotated = rot90(trimmed, 2)
            self.img.crop_area = self.img.auto_crop
        elif rotate == 270:
            rotated = rot90(trimmed, 3)
            self.img.crop_area = [
                self.img.trim_left,
                self.img.trim_up,
                self.img.trim_right,
                self.img.trim_down,
            ]
        else:
            rotated = trimmed
            self.img.crop_area = self.img.auto_crop
        return rotated

    def get_vacuum_points(self, rotation_angle: int) -> list[dict[str, int]]:
        """Calculate the calibration points based on the rotation angle."""

        """get_calibration_data"""

        vacuum_points = [
            {
                "x": self.img.crop_area[0] + self.img.offset_x,
                "y": self.img.crop_area[1] + self.img.offset_y,
            },  # Top-left corner 0
            {
                "x": self.img.crop_area[2] - self.img.offset_x,
                "y": self.img.crop_area[1] + self.img.offset_y,
            },  # Top-right corner 1
            {
                "x": self.img.crop_area[2] - self.img.offset_x,
                "y": self.img.crop_area[3] - self.img.offset_y,
            },  # Bottom-right corner 2
            {
                "x": self.img.crop_area[0] + self.img.offset_x,
                "y": self.img.crop_area[3] - self.img.offset_y,
            },  # Bottom-left corner (optional)3
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

        return vacuum_points

    def set_image_offset_ratio_1_1(self, width: int, height: int) -> None:
        """Set the image offset ratio to 1:1."""
        """async_map_coordinates_offset"""

        rotation = self.img.shared.image_rotate

        if rotation == 0 or rotation == 180:
            self.img.offset_y = self.img.crop_img_size[0] - width
            self.img.offset_x = (height - self.img.crop_img_size[1]) // 2
        elif rotation == 90 or rotation == 270:
            self.img.offset_y = width - self.img.crop_img_size[0]
            self.img.offset_x = (self.img.crop_img_size[1] - height) // 2
        _LOGGER.debug(
            f"{self.file_name} Image Coordinates: "
            f"Offset X: {self.img.offset_x} Offset Y: {self.img.offset_y}"
        )

    def set_image_offset_ratio_2_1(self, width: int, height: int) -> None:
        """Set the image offset ratio to 2:1."""
        """async_map_coordinates_offset"""

        rotation = self.img.shared.image_rotate

        if rotation == 0 or rotation == 180:
            self.img.offset_y = width - self.img.crop_img_size[0]
            self.img.offset_x = height - self.img.crop_img_size[1]
        elif rotation == 90 or rotation == 270:
            self.img.offset_x = width - self.img.crop_img_size[0]
            self.img.offset_y = height - self.img.crop_img_size[1]

        _LOGGER.debug(
            f"{self.file_name} Image Coordinates: "
            f"Offset X: {self.img.offset_x} Offset Y: {self.img.offset_y}"
        )

    def set_image_offset_ratio_3_2(self, width: int, height: int) -> None:
        """Set the image offset ratio to 3:2."""
        """async_map_coordinates_offset"""

        rotation = self.img.shared.image_rotate

        if rotation == 0 or rotation == 180:
            self.img.offset_y = width - self.img.crop_img_size[0]
            self.img.offset_x = ((height - self.img.crop_img_size[1]) // 2) - (
                self.img.crop_img_size[1] // 10
            )
        elif rotation == 90 or rotation == 270:
            self.img.offset_y = (self.img.crop_img_size[0] - width) // 2
            self.img.offset_x = (self.img.crop_img_size[1] - height) + (
                (height // 10) // 2
            )

        _LOGGER.debug(
            f"{self.file_name} Image Coordinates: "
            f"Offset X: {self.img.offset_x} Offset Y: {self.img.offset_y}"
        )

    def set_image_offset_ratio_5_4(self, width: int, height: int) -> None:
        """Set the image offset ratio to 5:4."""
        """async_map_coordinates_offset"""

        rotation = self.img.shared.image_rotate

        if rotation == 0 or rotation == 180:
            self.img.offset_x = ((width - self.img.crop_img_size[0]) // 2) - (
                self.img.crop_img_size[0] // 2
            )
            self.img.offset_y = (self.img.crop_img_size[1] - height) - (
                self.img.crop_img_size[1] // 2
            )
        elif rotation == 90 or rotation == 270:
            self.img.offset_y = ((self.img.crop_img_size[0] - width) // 2) - 10
            self.img.offset_x = (self.img.crop_img_size[1] - height) + (height // 10)

        _LOGGER.debug(
            f"{self.file_name} Image Coordinates: "
            f"Offset X: {self.img.offset_x} Offset Y: {self.img.offset_y}"
        )

    def set_image_offset_ratio_9_16(self, width: int, height: int) -> None:
        """Set the image offset ratio to 9:16."""
        """async_map_coordinates_offset"""

        rotation = self.img.shared.image_rotate

        if rotation == 0 or rotation == 180:
            self.img.offset_y = width - self.img.crop_img_size[0]
            self.img.offset_x = height - self.img.crop_img_size[1]
        elif rotation == 90 or rotation == 270:
            self.img.offset_x = (width - self.img.crop_img_size[0]) + (height // 10)
            self.img.offset_y = height - self.img.crop_img_size[1]

        _LOGGER.debug(
            f"{self.file_name} Image Coordinates: "
            f"Offset X: {self.img.offset_x} Offset Y: {self.img.offset_y}"
        )

    def set_image_offset_ratio_16_9(self, width: int, height: int) -> None:
        """Set the image offset ratio to 16:9."""
        """async_map_coordinates_offset"""

        rotation = self.img.shared.image_rotate

        if rotation == 0 or rotation == 180:
            self.img.offset_y = width - self.img.crop_img_size[0]
            self.img.offset_x = height - self.img.crop_img_size[1]
        elif rotation == 90 or rotation == 270:
            self.img.offset_x = width - self.img.crop_img_size[0]
            self.img.offset_y = height - self.img.crop_img_size[1]

        _LOGGER.debug(
            f"{self.file_name} Image Coordinates at 16:9: "
            f"Offset X: {self.img.offset_x} Offset Y: {self.img.offset_y}"
        )

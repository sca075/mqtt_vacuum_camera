"""Auto Crop Class for trimming and zooming images.
Version: 2024.08.2"""

from __future__ import annotations

import logging
import os

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR
import numpy as np
from numpy import rot90

from custom_components.mqtt_vacuum_camera.const import CAMERA_STORAGE
from custom_components.mqtt_vacuum_camera.types import Color, NumpyArray, TrimCropData
from custom_components.mqtt_vacuum_camera.utils.colors_man import color_grey
from custom_components.mqtt_vacuum_camera.utils.files_operations import (
    async_load_file,
    async_write_json_to_disk,
)

_LOGGER = logging.getLogger(__name__)


class TrimError(Exception):
    """Exception raised for errors in the trim process."""

    def __init__(self, message, image):
        super().__init__(message)
        self.image = image


class AutoCrop:
    """Auto Crop Class for trimming and zooming images."""

    def __init__(self, image_handler, hass: HomeAssistant):
        self.imh = image_handler
        self.hass = hass
        self.file_name = self.imh.file_name
        self.path_to_data = self.hass.config.path(
            STORAGE_DIR, CAMERA_STORAGE, f"auto_crop_{self.file_name}.json"
        )

    def check_trim(
        self, trimmed_height, trimmed_width, margin_size, image_array, file_name, rotate
    ):
        """Check if the trim is okay."""
        if trimmed_height <= margin_size or trimmed_width <= margin_size:
            self.imh.crop_area = [0, 0, image_array.shape[1], image_array.shape[0]]
            self.imh.img_size = (image_array.shape[1], image_array.shape[0])
            raise TrimError(
                f"{file_name}: Trimming failed at rotation {rotate}.", image_array
            )

    def _calculate_trimmed_dimensions(self):
        """Calculate and update the dimensions after trimming."""
        trimmed_width = max(
            0,
            (
                (self.imh.trim_right - self.imh.offset_right)
                - (self.imh.trim_left + self.imh.offset_left)
            ),
        )
        trimmed_height = max(
            0,
            (
                (self.imh.trim_down - self.imh.offset_bottom)
                - (self.imh.trim_up + self.imh.offset_top)
            ),
        )
        # Ensure shared reference dimensions are updated
        if hasattr(self.imh.shared, "image_ref_height") and hasattr(
            self.imh.shared, "image_ref_width"
        ):
            self.imh.shared.image_ref_height = trimmed_height
            self.imh.shared.image_ref_width = trimmed_width
        else:
            _LOGGER.warning(
                "Shared attributes for image dimensions are not initialized."
            )
        return trimmed_width, trimmed_height

    async def _async_auto_crop_data(self):
        """Load the auto crop data from the disk."""

        if os.path.exists(self.path_to_data) and not self.imh.auto_crop:
            try:
                temp_data = await async_load_file(self.path_to_data, True)
                if temp_data:
                    trims_data = TrimCropData.from_dict(dict(temp_data)).to_list()
                    (
                        self.imh.trim_left,
                        self.imh.trim_up,
                        self.imh.trim_right,
                        self.imh.trim_down,
                    ) = trims_data
                    self._calculate_trimmed_dimensions()
                    return trims_data
            except Exception as e:
                _LOGGER.debug(f"Failed to load trim data due to an error: {e}")
        return None

    def auto_crop_offset(self):
        """Calculate the offset for the auto crop."""
        if self.imh.auto_crop:
            self.imh.auto_crop[0] += self.imh.offset_left
            self.imh.auto_crop[1] += self.imh.offset_top
            self.imh.auto_crop[2] -= self.imh.offset_right
            self.imh.auto_crop[3] -= self.imh.offset_bottom

    async def _init_auto_crop(self):
        """Initialize the auto crop data."""
        if not self.imh.auto_crop:
            self.imh.auto_crop = await self._async_auto_crop_data()
            if self.imh.auto_crop:
                self.auto_crop_offset()
        return self.imh.auto_crop

    async def _async_save_auto_crop_data(self):
        """Save the auto crop data to the disk."""
        try:
            if not os.path.exists(self.path_to_data):
                data = TrimCropData(
                    self.imh.trim_left,
                    self.imh.trim_up,
                    self.imh.trim_right,
                    self.imh.trim_down,
                ).to_dict()
                await async_write_json_to_disk(self.path_to_data, data)
        except Exception as e:
            _LOGGER.error(f"Failed to save trim data due to an error: {e}")

    async def async_image_margins(
        self, image_array: NumpyArray, detect_colour: Color
    ) -> tuple[int, int, int, int]:
        """Crop the image based on the auto crop area."""
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

    async def async_check_if_zoom_is_on(
        self,
        image_array: NumpyArray,
        margin_size: int = 100,
        zoom: bool = False,
        rand256: bool = False,
    ) -> NumpyArray:
        """Check if the image need to be zoom."""

        if (
            zoom
            and self.imh.shared.vacuum_state == "cleaning"
            and self.imh.shared.image_auto_zoom
        ):
            # Zoom the image based on the robot's position.
            _LOGGER.debug(
                f"{self.file_name}: Zooming the image on room {self.imh.robot_in_room['room']}."
            )
            if rand256:
                trim_left = round(self.imh.robot_in_room["right"] / 10) - margin_size
                trim_right = round(self.imh.robot_in_room["left"] / 10) + margin_size
                trim_up = round(self.imh.robot_in_room["down"] / 10) - margin_size
                trim_down = round(self.imh.robot_in_room["up"] / 10) + margin_size
            else:
                trim_left = self.imh.robot_in_room["left"] - margin_size
                trim_right = self.imh.robot_in_room["right"] + margin_size
                trim_up = self.imh.robot_in_room["up"] - margin_size
                trim_down = self.imh.robot_in_room["down"] + margin_size
            trim_left, trim_right = sorted([trim_left, trim_right])
            trim_up, trim_down = sorted([trim_up, trim_down])
            trimmed = image_array[trim_up:trim_down, trim_left:trim_right]
        else:
            # Apply the auto-calculated trims to the rotated image
            trimmed = image_array[
                self.imh.auto_crop[1] : self.imh.auto_crop[3],
                self.imh.auto_crop[0] : self.imh.auto_crop[2],
            ]
        return trimmed

    async def async_rotate_the_image(
        self, trimmed: NumpyArray, rotate: int
    ) -> NumpyArray:
        """Rotate the image and return the new array."""
        if rotate == 90:
            rotated = rot90(trimmed)
            self.imh.crop_area = [
                self.imh.trim_left,
                self.imh.trim_up,
                self.imh.trim_right,
                self.imh.trim_down,
            ]
        elif rotate == 180:
            rotated = rot90(trimmed, 2)
            self.imh.crop_area = self.imh.auto_crop
        elif rotate == 270:
            rotated = rot90(trimmed, 3)
            self.imh.crop_area = [
                self.imh.trim_left,
                self.imh.trim_up,
                self.imh.trim_right,
                self.imh.trim_down,
            ]
        else:
            rotated = trimmed
            self.imh.crop_area = self.imh.auto_crop
        return rotated

    async def async_auto_trim_and_zoom_image(
        self,
        image_array: NumpyArray,
        detect_colour: Color = color_grey,
        margin_size: int = 0,
        rotate: int = 0,
        zoom: bool = False,
        rand256: bool = False,
    ):
        """
        Automatically crops and trims a numpy array and returns the processed image.
        """
        try:
            await self._init_auto_crop()
            if self.imh.auto_crop is None:
                _LOGGER.debug(f"{self.file_name}: Calculating auto trim box")
                # Find the coordinates of the first occurrence of a non-background color
                min_y, min_x, max_x, max_y = await self.async_image_margins(
                    image_array, detect_colour
                )
                # Calculate and store the trims coordinates with margins
                self.imh.trim_left = int(min_x) - margin_size
                self.imh.trim_up = int(min_y) - margin_size
                self.imh.trim_right = int(max_x) + margin_size
                self.imh.trim_down = int(max_y) + margin_size
                del min_y, min_x, max_x, max_y

                # Calculate the dimensions after trimming using min/max values
                trimmed_width, trimmed_height = self._calculate_trimmed_dimensions()

                # Test if the trims are okay or not
                try:
                    self.check_trim(
                        trimmed_height,
                        trimmed_width,
                        margin_size,
                        image_array,
                        self.file_name,
                        rotate,
                    )
                except TrimError as e:
                    return e.image

                # Store Crop area of the original image_array we will use from the next frame.
                self.imh.auto_crop = TrimCropData(
                    self.imh.trim_left,
                    self.imh.trim_up,
                    self.imh.trim_right,
                    self.imh.trim_down,
                ).to_list()
                if self.imh.shared.vacuum_state == "docked":
                    await self._async_save_auto_crop_data()  # Save the crop data to the disk
                self.auto_crop_offset()
            # If it is needed to zoom the image.
            trimmed = await self.async_check_if_zoom_is_on(
                image_array, margin_size, zoom, rand256
            )
            del image_array  # Free memory.
            # Rotate the cropped image based on the given angle
            rotated = await self.async_rotate_the_image(trimmed, rotate)
            del trimmed  # Free memory.
            _LOGGER.debug(f"{self.file_name}: Auto Trim Box data: {self.imh.crop_area}")
            self.imh.crop_img_size = [rotated.shape[1], rotated.shape[0]]
            _LOGGER.debug(
                f"{self.file_name}: Auto Trimmed image size: {self.imh.crop_img_size}"
            )

        except Exception as e:
            _LOGGER.warning(
                f"{self.file_name}: Error {e} during auto trim and zoom.",
                exc_info=True,
            )
            return None
        return rotated

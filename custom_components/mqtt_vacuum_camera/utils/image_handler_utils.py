"""
Image Utils Class for Valetudo Hypfer Image Handling.
This class is used to simplify the ImageHandler class.
Version: 2024.08.1
"""

from __future__ import annotations

import logging

from PIL import Image, ImageOps

_LOGGER = logging.getLogger(__name__)


class ImageUtils:
    """Image Utils Class for Valetudo Hypfer Image Handler."""

    """It is used to simplify the ImageHandler class."""

    def __init__(self, image_handler):
        self.img = image_handler
        self.file_name = self.img.shared.file_name

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

    def re_get_vacuum_points(self, rotation_angle: int) -> list[dict[str, int]]:
        """Recalculate the calibration points based on the rotation angle.
        RAND256 Vacuums Calibration Points are in 10th of a mm."""
        vacuum_points = [
            {
                "x": ((self.img.crop_area[0] + self.img.offset_x) * 10),
                "y": ((self.img.crop_area[1] + self.img.offset_y) * 10),
            },  # Top-left corner 0
            {
                "x": ((self.img.crop_area[2] - self.img.offset_x) * 10),
                "y": ((self.img.crop_area[1] + self.img.offset_y) * 10),
            },  # Top-right corner 1
            {
                "x": ((self.img.crop_area[2] - self.img.offset_x) * 10),
                "y": ((self.img.crop_area[3] - self.img.offset_y) * 10),
            },  # Bottom-right corner 2
            {
                "x": ((self.img.crop_area[0] + self.img.offset_x) * 10),
                "y": ((self.img.crop_area[3] - self.img.offset_y) * 10),
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

    def set_image_offset_ratio_1_1(
        self, width: int, height: int, rand256: bool = False
    ) -> None:
        """Set the image offset ratio to 1:1."""
        """async_map_coordinates_offset"""

        rotation = self.img.shared.image_rotate
        if not rand256:
            if rotation == 0 or rotation == 180:
                self.img.offset_y = self.img.crop_img_size[0] - width
                self.img.offset_x = (height - self.img.crop_img_size[1]) // 2
            elif rotation == 90 or rotation == 270:
                self.img.offset_y = width - self.img.crop_img_size[0]
                self.img.offset_x = (self.img.crop_img_size[1] - height) // 2
        else:
            if rotation == 0 or rotation == 180:
                self.img.offset_x = (width - self.img.crop_img_size[0]) // 2
                self.img.offset_y = height - self.img.crop_img_size[1]
            elif rotation == 90 or rotation == 270:
                self.img.offset_y = (self.img.crop_img_size[0] - width) // 2
                self.img.offset_x = self.img.crop_img_size[1] - height

        _LOGGER.debug(
            f"{self.file_name} Image Coordinates: "
            f"Offset X: {self.img.offset_x} Offset Y: {self.img.offset_y}"
        )

    def set_image_offset_ratio_2_1(
        self, width: int, height: int, rand256: bool = False
    ) -> None:
        """Set the image offset ratio to 2:1."""
        """async_map_coordinates_offset"""

        rotation = self.img.shared.image_rotate
        if not rand256:
            if rotation == 0 or rotation == 180:
                self.img.offset_y = width - self.img.crop_img_size[0]
                self.img.offset_x = height - self.img.crop_img_size[1]
            elif rotation == 90 or rotation == 270:
                self.img.offset_x = width - self.img.crop_img_size[0]
                self.img.offset_y = height - self.img.crop_img_size[1]
        else:
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

    def set_image_offset_ratio_3_2(
        self, width: int, height: int, rand256: bool = False
    ) -> None:
        """Set the image offset ratio to 3:2."""
        """async_map_coordinates_offset"""

        rotation = self.img.shared.image_rotate

        if not rand256:
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
        else:
            if rotation == 0 or rotation == 180:
                self.img.offset_x = (width - self.img.crop_img_size[0]) // 2
                self.img.offset_y = height - self.img.crop_img_size[1]
            elif rotation == 90 or rotation == 270:
                self.img.offset_y = (self.img.crop_img_size[0] - width) // 2
                self.img.offset_x = self.img.crop_img_size[1] - height

        _LOGGER.debug(
            f"{self.file_name} Image Coordinates: "
            f"Offset X: {self.img.offset_x} Offset Y: {self.img.offset_y}"
        )

    def set_image_offset_ratio_5_4(
        self, width: int, height: int, rand256: bool = False
    ) -> None:
        """Set the image offset ratio to 5:4."""
        """async_map_coordinates_offset"""

        rotation = self.img.shared.image_rotate
        if not rand256:
            if rotation == 0 or rotation == 180:
                self.img.offset_x = ((width - self.img.crop_img_size[0]) // 2) - (
                    self.img.crop_img_size[0] // 2
                )
                self.img.offset_y = (self.img.crop_img_size[1] - height) - (
                    self.img.crop_img_size[1] // 2
                )
            elif rotation == 90 or rotation == 270:
                self.img.offset_y = ((self.img.crop_img_size[0] - width) // 2) - 10
                self.img.offset_x = (self.img.crop_img_size[1] - height) + (
                    height // 10
                )
        else:
            if rotation == 0 or rotation == 180:
                self.img.offset_y = (width - self.img.crop_img_size[0]) // 2
                self.img.offset_x = self.img.crop_img_size[1] - height
            elif rotation == 90 or rotation == 270:
                self.img.offset_y = (self.img.crop_img_size[0] - width) // 2
                self.img.offset_x = self.img.crop_img_size[1] - height

        _LOGGER.debug(
            f"{self.file_name} Image Coordinates: "
            f"Offset X: {self.img.offset_x} Offset Y: {self.img.offset_y}"
        )

    def set_image_offset_ratio_9_16(
        self, width: int, height: int, rand256: bool = False
    ) -> None:
        """Set the image offset ratio to 9:16."""
        """async_map_coordinates_offset"""

        rotation = self.img.shared.image_rotate
        if not rand256:
            if rotation == 0 or rotation == 180:
                self.img.offset_y = width - self.img.crop_img_size[0]
                self.img.offset_x = height - self.img.crop_img_size[1]
            elif rotation == 90 or rotation == 270:
                self.img.offset_x = (width - self.img.crop_img_size[0]) + (height // 10)
                self.img.offset_y = height - self.img.crop_img_size[1]
        else:
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

    def set_image_offset_ratio_16_9(
        self, width: int, height: int, rand256: bool = False
    ) -> None:
        """Set the image offset ratio to 16:9."""
        """async_map_coordinates_offset"""

        rotation = self.img.shared.image_rotate
        if not rand256:
            if rotation == 0 or rotation == 180:
                self.img.offset_y = width - self.img.crop_img_size[0]
                self.img.offset_x = height - self.img.crop_img_size[1]
            elif rotation == 90 or rotation == 270:
                self.img.offset_x = width - self.img.crop_img_size[0]
                self.img.offset_y = height - self.img.crop_img_size[1]
        else:
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

    async def async_zone_propriety(self, zones_data) -> dict:
        """Get the zone propiety"""
        zone_properties = {}
        id_count = 1
        for zone in zones_data:
            zone_name = zone.get("name")
            coordinates = zone.get("coordinates")
            if coordinates and len(coordinates) > 0:
                coordinates[0].pop()
                x1, y1, x2, y2 = coordinates[0]
                zone_properties[zone_name] = {
                    "zones": coordinates,
                    "name": zone_name,
                    "x": ((x1 + x2) // 2),
                    "y": ((y1 + y2) // 2),
                }
                id_count += 1
            if id_count > 1:
                _LOGGER.debug(f"{self.file_name}: Zones Properties updated.")
        return zone_properties

    async def async_points_propriety(self, points_data) -> dict:
        """Get the point propiety"""
        point_properties = {}
        id_count = 1
        for point in points_data:
            point_name = point.get("name")
            coordinates = point.get("coordinates")
            if coordinates and len(coordinates) > 0:
                coordinates = point.get("coordinates")
                x1, y1 = coordinates
                point_properties[id_count] = {
                    "position": coordinates,
                    "name": point_name,
                    "x": x1,
                    "y": y1,
                }
                id_count += 1
            if id_count > 1:
                _LOGGER.debug(f"{self.file_name}: Point Properties updated.")
        return point_properties


async def resize_to_aspect_ratio(
    pil_img: Image,
    ref_width: int,
    ref_height: int,
    aspect_ratio: str = None,
    async_map_coordinates_offset=None,
) -> tuple:
    """
    Resize the image to match the given aspect ratio, maintaining the camera's aspect ratio.

    Args:
        pil_img (PIL.Image): The input image to resize.
        ref_width (int): The reference width for the image.
        ref_height (int): The reference height for the image.
        aspect_ratio (str): Aspect ratio in the format "width,height" or None for default.
        async_map_coordinates_offset (callable): Async function to compute coordinate offsets.

    Returns:
        tuple: A resized image and crop image size as a tuple (PIL.Image, list).
    """
    crop_img_size = [0, 0]

    if aspect_ratio and aspect_ratio != "None":
        try:
            # Parse aspect ratio (e.g., "16,9")
            wsf, hsf = [int(x) for x in aspect_ratio.split(",")]
            new_aspect_ratio = wsf / hsf

            # Calculate current aspect ratio
            current_aspect_ratio = ref_width / ref_height

            # Resize based on aspect ratio comparison
            if current_aspect_ratio > new_aspect_ratio:
                new_width = int(pil_img.height * new_aspect_ratio)
                new_height = pil_img.height
            else:
                new_width = pil_img.width
                new_height = int(pil_img.width / new_aspect_ratio)

            # Resize image using padding
            resized_img = ImageOps.pad(pil_img, (new_width, new_height))

            # Compute crop image size if mapping offset function is provided
            if async_map_coordinates_offset:
                (
                    crop_img_size[0],
                    crop_img_size[1],
                ) = await async_map_coordinates_offset(wsf, hsf, new_width, new_height)

            return resized_img, crop_img_size

        except Exception as e:
            raise ValueError(
                f"Error resizing image with aspect ratio {aspect_ratio}: {e}"
            )

    # If no aspect ratio is provided, return the original image and default crop size
    return pil_img, crop_img_size

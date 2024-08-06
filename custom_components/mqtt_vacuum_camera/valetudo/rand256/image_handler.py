"""
Image Handler Module for Valetudo Re Vacuums.
It returns the PIL PNG image frame relative to the Map Data extrapolated from the vacuum json.
It also returns calibration, rooms data to the card and other images information to the camera.
Version: v2024.08.0
"""

from __future__ import annotations

import logging
import os.path
import uuid

from PIL import Image, ImageOps
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR
import numpy as np

from custom_components.mqtt_vacuum_camera.const import CAMERA_STORAGE
from custom_components.mqtt_vacuum_camera.types import (
    Color,
    JsonType,
    NumpyArray,
    PilPNG,
    RobotPosition,
    RoomsProperties,
    TrimCropData,
)
from custom_components.mqtt_vacuum_camera.utils.colors_man import color_grey
from custom_components.mqtt_vacuum_camera.utils.drawable import Drawable
from custom_components.mqtt_vacuum_camera.utils.files_operations import (
    async_load_file,
    async_write_json_to_disk,
)
from custom_components.mqtt_vacuum_camera.utils.img_data import ImageData
from custom_components.mqtt_vacuum_camera.valetudo.hypfer.handler_utils import (
    ImageUtils as ImUtils,
    TrimError,
)

_LOGGER = logging.getLogger(__name__)


# noinspection PyTypeChecker
class ReImageHandler(object):
    """
    Image Handler for Valetudo Re Vacuums.
    """

    def __init__(self, camera_shared, hass: HomeAssistant):
        self.hass = hass
        self.auto_crop = None  # Auto crop flag
        self.segment_data = None  # Segment data
        self.outlines = None  # Outlines data
        self.calibration_data = None  # Calibration data
        self.charger_pos = None  # Charger position
        self.crop_area = None  # Crop area
        self.crop_img_size = None  # Crop image size
        self.data = ImageData  # Image Data
        self.draw = Drawable  # Drawable
        self.frame_number = 0  # Image Frame number
        self.go_to = None  # Go to position data
        self.img_base_layer = None  # Base image layer
        self.img_rotate = 0  # Image rotation
        self.img_size = None  # Image size
        self.json_data = None  # Json data
        self.json_id = None  # Json id
        self.path_pixels = None  # Path pixels data
        self.robot_in_room = None  # Robot in room data
        self.robot_pos = None  # Robot position
        self.room_propriety = None  # Room propriety data
        self.rooms_pos = None  # Rooms position data
        self.shared = camera_shared  # Shared data
        self.active_zones = None  # Active zones
        self.trim_down = None  # Trim down
        self.trim_left = None  # Trim left
        self.trim_right = None  # Trim right
        self.trim_up = None  # Trim up
        self.zooming = False  # Zooming flag
        self.file_name = self.shared.file_name  # File name
        self.path_to_data = self.hass.config.path(
            STORAGE_DIR, CAMERA_STORAGE, f"auto_crop_{self.file_name}.json"
        )  # path to the data
        self.offset_x = 0  # offset x for the aspect ratio.
        self.offset_y = 0  # offset y for the aspect ratio.
        self.offset_top = self.shared.offset_top  # offset top
        self.offset_bottom = self.shared.offset_down  # offset bottom
        self.offset_left = self.shared.offset_left  # offset left
        self.offset_right = self.shared.offset_right  # offset right
        self.imu = ImUtils(self)

    def check_trim(
        self, trimmed_height, trimmed_width, margin_size, image_array, file_name, rotate
    ):
        """
        Check if the trimming is okay.
        """
        if trimmed_height <= margin_size or trimmed_width <= margin_size:
            self.crop_area = [0, 0, image_array.shape[1], image_array.shape[0]]
            self.img_size = (image_array.shape[1], image_array.shape[0])
            raise TrimError(
                f"{file_name}: Trimming failed at rotation {rotate}.",
                image_array,
            )

    def _calculate_trimmed_dimensions(self):
        """Calculate and update the dimensions after trimming."""
        trimmed_width = max(
            0,
            (
                (self.trim_right - self.offset_right)
                - (self.trim_left + self.offset_left)
            ),
        )
        trimmed_height = max(
            0,
            ((self.trim_down - self.offset_bottom) - (self.trim_up + self.offset_top)),
        )

        # Ensure shared reference dimensions are updated
        if hasattr(self.shared, "image_ref_height") and hasattr(
            self.shared, "image_ref_width"
        ):
            self.shared.image_ref_height = trimmed_height
            self.shared.image_ref_width = trimmed_width
        else:
            _LOGGER.warning(
                "Shared attributes for image dimensions are not initialized."
            )
        return trimmed_width, trimmed_height

    async def _async_auto_crop_data(self):
        """Load the auto crop data from the disk."""
        try:
            if os.path.exists(self.path_to_data) and self.auto_crop is None:
                temp_data = await async_load_file(self.path_to_data, True)
                if temp_data is not None:
                    trims_data = TrimCropData.from_dict(dict(temp_data)).to_list()
                    self.trim_left, self.trim_up, self.trim_right, self.trim_down = (
                        trims_data
                    )

                    # Calculate the dimensions after trimming using min/max values
                    _, _ = self._calculate_trimmed_dimensions()
                    return trims_data
                else:
                    _LOGGER.error("Trim data file is empty.")
                    return None
        except Exception as e:
            _LOGGER.error(f"Failed to load trim data due to an error: {e}")
            return None

    def auto_crop_offset(self):
        """Calculate the crop offset."""
        if self.auto_crop:
            self.auto_crop[0] += self.offset_left
            self.auto_crop[1] += self.offset_top
            self.auto_crop[2] -= self.offset_right
            self.auto_crop[3] -= self.offset_bottom
        else:
            _LOGGER.warning(
                "Auto crop data is not available. Time Out Warning will occurs!"
            )
            self.auto_crop = None

    async def _init_auto_crop(self):
        if self.auto_crop is None:
            _LOGGER.debug(f"{self.file_name}: Trying to load crop data from disk")
            self.auto_crop = await self._async_auto_crop_data()
            self.auto_crop_offset()
        return self.auto_crop

    async def _async_save_auto_crop_data(self):
        """Save the auto crop data to the disk."""
        try:
            if not os.path.exists(self.path_to_data):
                _LOGGER.debug("Writing crop data to disk")
                data = TrimCropData(
                    self.trim_left, self.trim_up, self.trim_right, self.trim_down
                ).to_dict()
                await async_write_json_to_disk(self.path_to_data, data)
        except Exception as e:
            _LOGGER.error(f"Failed to save trim data due to an error: {e}")

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
            await self._init_auto_crop()
            if self.auto_crop is None:
                _LOGGER.debug(f"{self.file_name}: Calculating auto trim box")
                # Find the coordinates of the first occurrence of a non-background color
                min_y, min_x, max_x, max_y = await self.imu.async_image_margins(
                    image_array, detect_colour
                )
                # Calculate and store the trims coordinates with margins
                self.trim_left = int(min_x) - margin_size
                self.trim_up = int(min_y) - margin_size
                self.trim_right = int(max_x) + margin_size
                self.trim_down = int(max_y) + margin_size
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
                self.auto_crop = TrimCropData(
                    self.trim_left, self.trim_up, self.trim_right, self.trim_down
                ).to_list()
                await self._async_save_auto_crop_data()  # Save the crop data to the disk
                self.auto_crop_offset()
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

    async def extract_room_properties(
        self, json_data: JsonType, destinations: JsonType
    ) -> RoomsProperties:
        """Extract the room properties."""
        unsorted_id = ImageData.get_rrm_segments_ids(json_data)
        size_x, size_y = ImageData.get_rrm_image_size(json_data)
        top, left = ImageData.get_rrm_image_position(json_data)
        if not self.segment_data or not self.outlines:
            self.segment_data, self.outlines = await ImageData.async_get_rrm_segments(
                json_data, size_x, size_y, top, left, True
            )
        try:
            dest_json = destinations
            room_data = dict(dest_json).get("rooms", [])
            zones_data = dict(dest_json).get("zones", [])
            points_data = dict(dest_json).get("spots", [])
            room_id_to_data = {room["id"]: room for room in room_data}
            self.rooms_pos = []
            room_properties = {}
            zone_properties = {}
            point_properties = {}
            if self.outlines:
                for id_x, room_id in enumerate(unsorted_id):
                    if room_id in room_id_to_data:
                        room_info = room_id_to_data[room_id]
                        name = room_info.get("name")
                        # Calculate x and y min/max from outlines
                        x_min = self.outlines[id_x][0][0]
                        x_max = self.outlines[id_x][1][0]
                        y_min = self.outlines[id_x][0][1]
                        y_max = self.outlines[id_x][1][1]
                        corners = [
                            (x_min, y_min),
                            (x_max, y_min),
                            (x_max, y_max),
                            (x_min, y_max),
                        ]
                        # rand256 vacuums accept int(room_id) or str(name)
                        # the card will soon support int(room_id) but the camera will send name
                        # this avoids the manual change of the values in the card.
                        self.rooms_pos.append(
                            {
                                "name": name,
                                "corners": corners,
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
        except Exception as e:
            _LOGGER.warning(
                f"{self.file_name} : Error in extract_room_properties: {e}",
                exc_info=True,
            )
            return None, None, None

    async def get_image_from_rrm(
        self,
        m_json: JsonType,  # json data
        destinations: None = None,  # MQTT destinations for labels
    ) -> PilPNG or None:
        """Generate Images from the json data."""
        color_wall: Color = self.shared.user_colors[0]
        color_no_go: Color = self.shared.user_colors[6]
        color_go_to: Color = self.shared.user_colors[7]
        color_robot: Color = self.shared.user_colors[2]
        color_charger: Color = self.shared.user_colors[5]
        color_move: Color = self.shared.user_colors[4]
        color_background: Color = self.shared.user_colors[3]
        color_zone_clean: Color = self.shared.user_colors[1]
        self.active_zones = self.shared.rand256_active_zone

        try:
            if (m_json is not None) and (not isinstance(m_json, tuple)):
                _LOGGER.info(self.file_name + ":Composing the image for the camera.")
                # buffer json data
                self.json_data = m_json
                if self.room_propriety:
                    _LOGGER.info(self.file_name + ": Supporting Rooms Cleaning!")
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
                charger_pos = self.data.rrm_coordinates_to_valetudo(
                    self.data.get_rrm_charger_position(m_json)
                )
                zone_clean = self.data.get_rrm_currently_cleaned_zones(m_json)
                no_go_area = self.data.get_rrm_forbidden_zones(m_json)
                virtual_walls = self.data.get_rrm_virtual_walls(m_json)
                path_pixel = self.data.get_rrm_path(m_json)
                path_pixel2 = self.data.sublist_join(
                    self.data.rrm_valetudo_path_array(path_pixel["points"]), 2
                )
                robot_position = None
                robot_position_angle = None
                # convert the data to reuse the current drawing library
                robot_pos = self.data.rrm_coordinates_to_valetudo(robot_pos)
                if robot_pos:
                    robot_position = robot_pos
                    angle = self.data.get_rrm_robot_angle(m_json)
                    robot_position_angle = round(angle[0], 0)
                    _LOGGER.debug(
                        f"robot position: {robot_pos}, robot angle: {robot_position_angle}"
                    )
                    if self.rooms_pos is None:
                        self.robot_pos = {
                            "x": robot_position[0] * 10,
                            "y": robot_position[1] * 10,
                            "angle": robot_position_angle,
                        }
                    else:
                        self.robot_pos = await self.async_get_robot_in_room(
                            (robot_position[0] * 10),
                            (robot_position[1] * 10),
                            robot_position_angle,
                        )
                _LOGGER.debug("charger position: %s", charger_pos)
                if charger_pos:
                    self.charger_pos = {
                        "x": (charger_pos[0] * 10),
                        "y": (charger_pos[1] * 10),
                    }

                pixel_size = 5
                room_id = 0
                if self.frame_number == 0:
                    _LOGGER.info(self.file_name + ": Empty image with background color")
                    img_np_array = await self.draw.create_empty_image(
                        5120, 5120, color_background
                    )
                    _LOGGER.info(self.file_name + ": Overlapping Layers")
                    # this below are floor data
                    pixels = self.data.from_rrm_to_compressed_pixels(
                        floor_data,
                        image_width=size_x,
                        image_height=size_y,
                        image_top=pos_top,
                        image_left=pos_left,
                    )
                    # checking if there are segments too (sorted pixels in the raw data).
                    if not self.segment_data:
                        self.segment_data, self.outlines = (
                            await self.data.async_get_rrm_segments(
                                m_json, size_x, size_y, pos_top, pos_left, True
                            )
                        )

                    if (self.segment_data and pixels) or pixels:
                        room_color = self.shared.rooms_colors[room_id]
                        # drawing floor
                        if pixels:
                            img_np_array = await self.draw.from_json_to_image(
                                img_np_array, pixels, pixel_size, room_color
                            )
                        # drawing segments floor
                        room_id = 0
                        rooms_list = [color_wall]
                        if self.segment_data:
                            _LOGGER.info(
                                f"{self.file_name}: Drawing segments >>>>>>>>>>>>>< "
                            )
                            for pixels in self.segment_data:
                                room_color = self.shared.rooms_colors[room_id]
                                rooms_list.append(room_color)
                                _LOGGER.debug(
                                    f"Room {room_id} color: {room_color}",
                                    {tuple(self.active_zones)},
                                )
                                if (
                                    self.active_zones
                                    and len(self.active_zones) > room_id
                                    and self.active_zones[room_id] == 1
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
                                room_id += 1
                                if room_id > 15:
                                    room_id = 0

                    _LOGGER.info(self.file_name + ": Completed floor Layers")
                    # Drawing walls.
                    walls = self.data.from_rrm_to_compressed_pixels(
                        walls_data,
                        image_width=size_x,
                        image_height=size_y,
                        image_left=pos_left,
                        image_top=pos_top,
                    )
                    if walls:
                        img_np_array = await self.draw.from_json_to_image(
                            img_np_array, walls, pixel_size, color_wall
                        )
                        _LOGGER.info(self.file_name + ": Completed base Layers")
                    if (room_id > 0) and not self.room_propriety:
                        self.room_propriety = await self.get_rooms_attributes(
                            destinations
                        )
                        if self.rooms_pos:
                            self.robot_pos = await self.async_get_robot_in_room(
                                (robot_position[0] * 10),
                                (robot_position[1] * 10),
                                robot_position_angle,
                            )
                    self.img_base_layer = await self.async_copy_array(img_np_array)

                # If there is a zone clean we draw it now.
                self.frame_number += 1
                img_np_array = await self.async_copy_array(self.img_base_layer)
                _LOGGER.debug(self.file_name + ": Frame number %s", self.frame_number)
                if self.frame_number > 5:
                    self.frame_number = 0
                # All below will be drawn each time
                # charger
                if charger_pos:
                    img_np_array = await self.draw.battery_charger(
                        img_np_array, charger_pos[0], charger_pos[1], color_charger
                    )
                # zone clean
                if zone_clean:
                    img_np_array = await self.draw.zones(
                        img_np_array, zone_clean, color_zone_clean
                    )
                # no-go zones
                if no_go_area:
                    img_np_array = await self.draw.zones(
                        img_np_array, no_go_area, color_no_go
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
                            img_np_array, predicted_path, 3, color_grey
                        )
                # draw the robot
                if robot_position and robot_position_angle:
                    img_np_array = await self.draw.robot(
                        img_np_array,
                        robot_position[0],
                        robot_position[1],
                        robot_position_angle,
                        color_robot,
                        self.file_name,
                    )
                _LOGGER.debug(
                    f"{self.file_name}:"
                    f" Auto cropping the image with rotation {int(self.shared.image_rotate)}"
                )
                img_np_array = await self.async_auto_trim_and_zoom_image(
                    img_np_array,
                    color_background,
                    int(self.shared.margins),
                    int(self.shared.image_rotate),
                    self.zooming,
                )
                pil_img = Image.fromarray(img_np_array, mode="RGBA")
                del img_np_array  # unload memory
                # reduce the image size if the zoomed image is bigger then the original.
                if (
                    self.shared.image_auto_zoom
                    and self.shared.vacuum_state == "cleaning"
                    and self.shared.image_zoom_lock_ratio
                    or self.shared.image_aspect_ratio != "None"
                ):
                    width = pil_img.width
                    height = pil_img.height
                    if (
                        self.shared.image_aspect_ratio != "None"
                        and width > 0
                        and height > 0
                    ):
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
                        return resized
                    else:
                        return ImageOps.pad(pil_img, (width, height))
                return pil_img

        except Exception as e:
            _LOGGER.warning(
                f"{self.file_name} : Error in get_image_from_json: {e}",
                exc_info=True,
            )
            return None

    def get_frame_number(self) -> int:
        """Return the frame number."""
        return self.frame_number

    def get_robot_position(self) -> any:
        """Return the robot position."""
        return self.robot_pos

    def get_charger_position(self) -> any:
        """Return the charger position."""
        return self.charger_pos

    def get_img_size(self) -> any:
        """Return the image size."""
        return self.img_size

    def get_json_id(self) -> str:
        """Return the json id."""
        return self.json_id

    async def get_rooms_attributes(
        self, destinations: JsonType = None
    ) -> RoomsProperties:
        """Return the rooms attributes."""
        if self.room_propriety:
            return self.room_propriety
        if self.json_data and destinations:
            _LOGGER.debug("Checking for rooms data..")
            self.room_propriety = await self.extract_room_properties(
                self.json_data, destinations
            )
            if self.room_propriety:
                _LOGGER.debug("Got Rooms Attributes.")
        return self.room_propriety

    async def async_get_robot_in_room(
        self, robot_x: int, robot_y: int, angle: float
    ) -> RobotPosition:
        """Get the robot position and return in what room is."""
        if self.robot_in_room:
            # Check if the robot coordinates are inside the room's corners
            if (
                (self.robot_in_room["left"] >= robot_x)
                and (self.robot_in_room["right"] <= robot_x)
            ) and (
                (self.robot_in_room["up"] >= robot_y)
                and (self.robot_in_room["down"] <= robot_y)
            ):
                temp = {
                    "x": robot_x,
                    "y": robot_y,
                    "angle": angle,
                    "in_room": self.robot_in_room["room"],
                }
                return temp
        # else we need to search and use the async method
        _LOGGER.debug(f"{self.file_name} changed room.. searching..")
        room_count = 0
        last_room = None
        if self.rooms_pos:
            if self.robot_in_room:
                last_room = self.robot_in_room
            for room in self.rooms_pos:
                corners = room["corners"]
                self.robot_in_room = {
                    "id": room_count,
                    "left": corners[0][0],
                    "right": corners[2][0],
                    "up": corners[0][1],
                    "down": corners[2][1],
                    "room": room["name"],
                }
                room_count += 1
                # Check if the robot coordinates are inside the room's corners
                if (
                    (self.robot_in_room["left"] >= robot_x)
                    and (self.robot_in_room["right"] <= robot_x)
                ) and (
                    (self.robot_in_room["up"] >= robot_y)
                    and (self.robot_in_room["down"] <= robot_y)
                ):
                    temp = {
                        "x": robot_x,
                        "y": robot_y,
                        "angle": angle,
                        "in_room": self.robot_in_room["room"],
                    }
                    _LOGGER.debug(
                        f"{self.file_name} is in {self.robot_in_room['room']}"
                    )
                    del room, corners, robot_x, robot_y  # free memory.
                    return temp
            del room, corners  # free memory.
            _LOGGER.debug(
                f"{self.file_name} not located within Camera Rooms coordinates."
            )
            self.zooming = False
            self.robot_in_room = last_room
            temp = {
                "x": robot_x,
                "y": robot_y,
                "angle": angle,
                "in_room": self.robot_in_room["room"],
            }
            return temp

    def get_calibration_data(self, rotation_angle: int = 0) -> any:
        """Return the map calibration data."""
        if not self.calibration_data:
            self.calibration_data = []
            self.img_rotate = rotation_angle
            _LOGGER.info(f"Getting Calibrations points {self.crop_area}")
            # Calculate the calibration points in the vacuum coordinate system
            # Valetudo Re version need corrections of the coordinates and are implemented with *10

            vacuum_points = [
                {
                    "x": ((self.crop_area[0] + self.offset_x) * 10),
                    "y": ((self.crop_area[1] + self.offset_y) * 10),
                },  # Top-left corner 0
                {
                    "x": ((self.crop_area[2] - self.offset_x) * 10),
                    "y": ((self.crop_area[1] + self.offset_y) * 10),
                },  # Top-right corner 1
                {
                    "x": ((self.crop_area[2] - self.offset_x) * 10),
                    "y": ((self.crop_area[3] - self.offset_y) * 10),
                },  # Bottom-right corner 2
                {
                    "x": ((self.crop_area[0] + self.offset_x) * 10),
                    "y": ((self.crop_area[3] - self.offset_y) * 10),
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

    async def async_map_coordinates_offset(
        self, wsf: int, hsf: int, width: int, height: int
    ) -> tuple[int, int]:
        """
        Convert the coordinates to the map.
        :param wsf: Width scale factor.
        :param hsf: Height scale factor.
        :param width: Width of the image.
        :param height: Height of the image.
        """

        rotation = self.shared.image_rotate

        _LOGGER.debug(f"Image Size: Width: {width} Height: {height}")
        _LOGGER.debug(
            f"Trimmed Image Size: Width: {self.crop_img_size[0]} Height: {self.crop_img_size[1]}"
        )
        if wsf == 1 and hsf == 1:
            if rotation == 0 or rotation == 180:
                self.offset_y = (width - self.crop_img_size[0]) // 2
                self.offset_x = self.crop_img_size[1] - height
            elif rotation == 90 or rotation == 270:
                self.offset_y = (self.crop_img_size[0] - width) // 2
                self.offset_x = self.crop_img_size[1] - height
            _LOGGER.debug(
                f"Coordinates: Offset X: {self.offset_x} Offset Y: {self.offset_y}"
            )
            return width, height
        elif wsf == 2 and hsf == 1:
            if rotation == 0 or rotation == 180:
                self.offset_y = width - self.crop_img_size[0]
                self.offset_x = height - self.crop_img_size[1]
            elif rotation == 90 or rotation == 270:
                self.offset_x = width - self.crop_img_size[0]
                self.offset_y = height - self.crop_img_size[1]
            _LOGGER.debug(
                f"Coordinates: Offset X: {self.offset_x} Offset Y: {self.offset_y}"
            )
            return width, height
        elif wsf == 3 and hsf == 2:
            if rotation == 0 or rotation == 180:
                self.offset_x = (width - self.crop_img_size[0]) // 2
                self.offset_y = height - self.crop_img_size[1]
            elif rotation == 90 or rotation == 270:
                self.offset_y = (self.crop_img_size[0] - width) // 2
                self.offset_x = self.crop_img_size[1] - height
            _LOGGER.debug(
                f"Coordinates: Offset X: {self.offset_x} Offset Y: {self.offset_y}"
            )
            return width, height
        elif wsf == 5 and hsf == 4:
            if rotation == 0 or rotation == 180:
                self.offset_y = (width - self.crop_img_size[0]) // 2
                self.offset_x = self.crop_img_size[1] - height
            elif rotation == 90 or rotation == 270:
                self.offset_y = (self.crop_img_size[0] - width) // 2
                self.offset_x = self.crop_img_size[1] - height
            _LOGGER.debug(
                f"Coordinates: Offset X: {self.offset_x} Offset Y: {self.offset_y}"
            )
            return width, height
        elif wsf == 9 and hsf == 16:
            if rotation == 0 or rotation == 180:
                self.offset_y = width - self.crop_img_size[0]
                self.offset_x = height - self.crop_img_size[1]
            elif rotation == 90 or rotation == 270:
                self.offset_x = width - self.crop_img_size[0]
                self.offset_y = height - self.crop_img_size[1]
            _LOGGER.debug(
                f"Coordinates: Offset X: {self.offset_x} Offset Y: {self.offset_y}"
            )
            return width, height
        elif wsf == 16 and hsf == 9:
            if rotation == 0 or rotation == 180:
                self.offset_y = width - self.crop_img_size[0]
                self.offset_x = height - self.crop_img_size[1]
            elif rotation == 90 or rotation == 270:
                self.offset_x = width - self.crop_img_size[0]
                self.offset_y = height - self.crop_img_size[1]
            _LOGGER.debug(
                f"Coordinates: Offset X: {self.offset_x} Offset Y: {self.offset_y}"
            )
            return width, height
        else:
            return width, height

    async def async_copy_array(self, original_array: NumpyArray) -> NumpyArray:
        """Copy the numpy array."""
        _LOGGER.debug(f"{self.file_name}: Copying the array.")
        return np.copy(original_array)

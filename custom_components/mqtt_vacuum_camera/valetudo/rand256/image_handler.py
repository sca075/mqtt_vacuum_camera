"""
Image Handler Module for Valetudo Re Vacuums.
It returns the PIL PNG image frame relative to the Map Data extrapolated from the vacuum json.
It also returns calibration, rooms data to the card and other images information to the camera.
Version: v2024.08.2
"""

from __future__ import annotations

import logging
import uuid

from PIL import Image, ImageOps
from homeassistant.core import HomeAssistant

from custom_components.mqtt_vacuum_camera.const import (
    DEFAULT_IMAGE_SIZE,
    DEFAULT_PIXEL_SIZE,
)
from custom_components.mqtt_vacuum_camera.types import (
    Color,
    JsonType,
    PilPNG,
    RobotPosition,
    RoomsProperties,
)
from custom_components.mqtt_vacuum_camera.utils.auto_crop import AutoCrop
from custom_components.mqtt_vacuum_camera.utils.handler_utils import (
    ImageUtils as ImUtils,
)
from custom_components.mqtt_vacuum_camera.utils.img_data import ImageData

from .reimg_draw import ImageDraw

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
        self.frame_number = 0  # Image Frame number
        self.go_to = None  # Go to position data
        self.img_base_layer = None  # Base image layer
        self.img_rotate = camera_shared.image_rotate  # Image rotation
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
        self.offset_x = 0  # offset x for the aspect ratio.
        self.offset_y = 0  # offset y for the aspect ratio.
        self.offset_top = self.shared.offset_top  # offset top
        self.offset_bottom = self.shared.offset_down  # offset bottom
        self.offset_left = self.shared.offset_left  # offset left
        self.offset_right = self.shared.offset_right  # offset right
        self.imd = ImageDraw(self)  # Image Draw
        self.imu = ImUtils(self)  # Image Utils
        self.ac = AutoCrop(self, self.hass)

    async def extract_room_properties(
        self, json_data: JsonType, destinations: JsonType
    ) -> RoomsProperties:
        """Extract the room properties."""
        unsorted_id = ImageData.get_rrm_segments_ids(json_data)
        size_x, size_y = ImageData.get_rrm_image_size(json_data)
        top, left = ImageData.get_rrm_image_position(json_data)
        try:
            if not self.segment_data or not self.outlines:
                self.segment_data, self.outlines = (
                    await ImageData.async_get_rrm_segments(
                        json_data, size_x, size_y, top, left, True
                    )
                )
            dest_json = destinations
            room_data = dict(dest_json).get("rooms", [])
            zones_data = dict(dest_json).get("zones", [])
            points_data = dict(dest_json).get("spots", [])
            room_id_to_data = {room["id"]: room for room in room_data}
            self.rooms_pos = []
            room_properties = {}
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
                # get the zones and points data
                zone_properties = await self.imu.async_zone_propriety(zones_data)
                # get the points data
                point_properties = await self.imu.async_points_propriety(points_data)

                if room_properties != {}:
                    if zone_properties != {}:
                        _LOGGER.debug("Rooms and Zones, data extracted!")
                    else:
                        _LOGGER.debug("Rooms, data extracted!")
                elif zone_properties != {}:
                    _LOGGER.debug("Zones, data extracted!")
                else:
                    self.rooms_pos = None
                    _LOGGER.debug(
                        f"{self.file_name}: Rooms and Zones data not available!"
                    )
                return room_properties, zone_properties, point_properties
        except Exception as e:
            _LOGGER.debug(
                f"No rooms Data or Error in extract_room_properties: {e}",
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
                _LOGGER.info(f"{self.file_name}: Composing the image for the camera.")
                # buffer json data
                self.json_data = m_json
                # get the image size
                size_x, size_y = self.data.get_rrm_image_size(m_json)
                ##########################
                self.img_size = DEFAULT_IMAGE_SIZE
                ###########################
                self.json_id = str(uuid.uuid4())  # image id
                _LOGGER.info(f"Vacuum Data ID: {self.json_id}")
                # get the robot position
                robot_pos, robot_position, robot_position_angle = (
                    await self.imd.async_get_robot_position(m_json)
                )
                if self.frame_number == 0:
                    room_id, img_np_array = await self.imd.async_draw_base_layer(
                        m_json,
                        size_x,
                        size_y,
                        color_wall,
                        color_zone_clean,
                        color_background,
                        DEFAULT_PIXEL_SIZE,
                    )
                    _LOGGER.info(f"{self.file_name}: Completed base Layers")
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
                    self.img_base_layer = await self.imd.async_copy_array(img_np_array)

                # If there is a zone clean we draw it now.
                self.frame_number += 1
                img_np_array = await self.imd.async_copy_array(self.img_base_layer)
                _LOGGER.debug(f"{self.file_name}: Frame number {self.frame_number}")
                if self.frame_number > 5:
                    self.frame_number = 0
                # All below will be drawn each time
                # charger
                img_np_array, self.charger_pos = await self.imd.async_draw_charger(
                    img_np_array, m_json, color_charger
                )
                # zone clean
                img_np_array = await self.imd.async_draw_zones(
                    m_json, img_np_array, color_zone_clean
                )
                # virtual walls
                img_np_array = await self.imd.async_draw_virtual_restrictions(
                    m_json, img_np_array, color_no_go
                )
                # draw path
                img_np_array = await self.imd.async_draw_path(
                    img_np_array, m_json, color_move
                )
                # go to flag and predicted path
                await self.imd.async_draw_go_to_flag(img_np_array, m_json, color_go_to)
                # draw the robot
                img_np_array = await self.imd.async_draw_robot_on_map(
                    img_np_array, robot_position, robot_position_angle, color_robot
                )
                _LOGGER.debug(
                    f"{self.file_name}:"
                    f" Auto cropping the image with rotation {int(self.shared.image_rotate)}"
                )
                img_np_array = await self.ac.async_auto_trim_and_zoom_image(
                    img_np_array,
                    color_background,
                    int(self.shared.margins),
                    int(self.shared.image_rotate),
                    self.zooming,
                    rand256=True,
                )
                pil_img = Image.fromarray(img_np_array, mode="RGBA")
                del img_np_array  # free memory
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
                        _LOGGER.debug(f"Aspect Ratio: {wsf}, {hsf}")
                        if wsf == 0 or hsf == 0:
                            return pil_img
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
        except (RuntimeError, RuntimeWarning) as e:
            _LOGGER.warning(
                f"{self.file_name}: Error {e} during image creation.",
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

        def _check_robot_position(x: int, y: int) -> bool:
            x_in_room = (self.robot_in_room["left"] >= x) and (
                self.robot_in_room["right"] <= x
            )
            y_in_room = (self.robot_in_room["up"] >= y) and (
                self.robot_in_room["down"] <= y
            )
            if x_in_room and y_in_room:
                return True
            return False

        # Check if the robot coordinates are inside the room's
        if self.robot_in_room and _check_robot_position(robot_x, robot_y):
            temp = {
                "x": robot_x,
                "y": robot_y,
                "angle": angle,
                "in_room": self.robot_in_room["room"],
            }
            self.active_zones = self.shared.rand256_active_zone
            if self.active_zones and (
                (self.robot_in_room["id"]) in range(len(self.active_zones))
            ):  # issue #100 Index out of range
                self.zooming = bool(self.active_zones[(self.robot_in_room["id"])])
            else:
                self.zooming = False

            return temp
        # else we need to search and use the async method
        _LOGGER.debug(f"{self.file_name} changed room.. searching..")
        room_count = -1
        last_room = None
        if self.rooms_pos:
            if self.robot_in_room:
                last_room = self.robot_in_room
            for room in self.rooms_pos:
                corners = room["corners"]
                room_count += 1
                self.robot_in_room = {
                    "id": room_count,
                    "left": corners[0][0],
                    "right": corners[2][0],
                    "up": corners[0][1],
                    "down": corners[2][1],
                    "room": room["name"],
                }
                # Check if the robot coordinates are inside the room's corners
                if _check_robot_position(robot_x, robot_y):
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
                f"{self.file_name}: Not located within Camera Rooms coordinates."
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
            _LOGGER.info(
                f"{self.file_name}: Getting Calibrations points {self.crop_area}"
            )

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

            # Valetudo Re version need corrections of the coordinates and are implemented with *10
            vacuum_points = self.imu.re_get_vacuum_points(rotation_angle)

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
        Offset the coordinates to the map.
        """

        if wsf == 1 and hsf == 1:
            self.imu.set_image_offset_ratio_1_1(width, height, rand256=True)
            return width, height
        elif wsf == 2 and hsf == 1:
            self.imu.set_image_offset_ratio_2_1(width, height, rand256=True)
            return width, height
        elif wsf == 3 and hsf == 2:
            self.imu.set_image_offset_ratio_3_2(width, height, rand256=True)
            return width, height
        elif wsf == 5 and hsf == 4:
            self.imu.set_image_offset_ratio_5_4(width, height, rand256=True)
            return width, height
        elif wsf == 9 and hsf == 16:
            self.imu.set_image_offset_ratio_9_16(width, height, rand256=True)
            return width, height
        elif wsf == 16 and hsf == 9:
            self.imu.set_image_offset_ratio_16_9(width, height, rand256=True)
            return width, height
        else:
            return width, height

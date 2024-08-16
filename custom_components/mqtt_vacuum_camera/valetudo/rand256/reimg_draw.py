"""
Image Draw Class for Valetudo Rand256 Image Handling.
This class is used to simplify the ImageHandler class.
Version: 2024.08.1
"""

from __future__ import annotations

import hashlib
import json
import logging

from custom_components.mqtt_vacuum_camera.types import Color, JsonType, NumpyArray
from custom_components.mqtt_vacuum_camera.utils.colors_man import color_grey
from custom_components.mqtt_vacuum_camera.utils.drawable import Drawable
from custom_components.mqtt_vacuum_camera.utils.img_data import ImageData

_LOGGER = logging.getLogger(__name__)


class ImageDraw:
    """Class to handle the image creation."""

    """It Draws each elements of the images, like the walls, zones, paths, etc."""

    def __init__(self, image_handler):
        self.img_h = image_handler
        self.file_name = self.img_h.shared.file_name
        self.data = ImageData
        self.draw = Drawable

    async def async_draw_go_to_flag(
        self, np_array: NumpyArray, m_json: JsonType, color_go_to: Color
    ) -> NumpyArray:
        """Draw the goto target flag on the map."""
        try:
            go_to = self.data.get_rrm_goto_target(m_json)
            if go_to:
                np_array = await self.draw.go_to_flag(
                    np_array,
                    (go_to[0], go_to[1]),
                    self.img_h.img_rotate,
                    color_go_to,
                )
                predicted_path = self.data.get_rrm_goto_predicted_path(m_json)
                if predicted_path:
                    np_array = await self.draw.lines(
                        np_array, predicted_path, 3, color_grey
                    )
                return np_array
            else:
                return np_array
        except Exception as e:
            _LOGGER.warning(
                f"{self.file_name}: Error in extraction of go to. {e}", exc_info=True
            )
            return np_array

    async def async_segment_data(
        self, m_json, size_x, size_y, pos_top, pos_left
    ) -> None:
        """Get the segments data from the JSON data."""
        try:
            if not self.img_h.segment_data:
                self.img_h.segment_data, self.img_h.outlines = (
                    await self.data.async_get_rrm_segments(
                        m_json, size_x, size_y, pos_top, pos_left, True
                    )
                )
        except ValueError as e:
            self.img_h.segment_data = None
            _LOGGER.info(f"{self.file_name}: No segments data found. {e}")

    async def async_draw_base_layer(
        self,
        m_json,
        size_x,
        size_y,
        color_wall,
        color_zone_clean,
        color_background,
        pixel_size,
    ):
        """Draw the base layer of the map."""
        pos_top, pos_left = self.data.get_rrm_image_position(m_json)
        walls_data = self.data.get_rrm_walls(m_json)
        floor_data = self.data.get_rrm_floor(m_json)

        _LOGGER.info(self.file_name + ": Empty image with background color")
        img_np_array = await self.draw.create_empty_image(
            self.img_h.img_size["x"], self.img_h.img_size["y"], color_background
        )
        room_id = 0
        if self.img_h.frame_number == 0:
            _LOGGER.info(self.file_name + ": Overlapping Layers")

            # checking if there are segments too (sorted pixels in the raw data).
            await self.async_segment_data(m_json, size_x, size_y, pos_top, pos_left)

            img_np_array = await self._draw_floor(
                img_np_array, floor_data, size_x, size_y, pos_top, pos_left, pixel_size
            )
            room_id, img_np_array = await self._draw_segments(
                img_np_array,
                pixel_size,
                self.img_h.segment_data,
                color_wall,
                color_zone_clean,
            )
            img_np_array = await self._draw_walls(
                img_np_array,
                walls_data,
                size_x,
                size_y,
                pos_top,
                pos_left,
                pixel_size,
                color_wall,
            )
        return room_id, img_np_array

    async def _draw_floor(
        self, img_np_array, floor_data, size_x, size_y, pos_top, pos_left, pixel_size
    ):
        """Draw the floor data onto the image."""
        pixels = self.data.from_rrm_to_compressed_pixels(
            floor_data,
            image_width=size_x,
            image_height=size_y,
            image_top=pos_top,
            image_left=pos_left,
        )
        if pixels:
            room_color = self.img_h.shared.rooms_colors[0]  # Using initial room_id = 0
            img_np_array = await self.draw.from_json_to_image(
                img_np_array, pixels, pixel_size, room_color
            )
        return img_np_array

    async def _draw_segments(
        self, img_np_array, pixel_size, segment_data, color_wall, color_zone_clean
    ):
        """Draw the segments onto the image and update room_id."""

        room_id = 0
        rooms_list = [color_wall]
        _LOGGER.info(f"{self.file_name}: Drawing segments. {len(segment_data)}")
        if not segment_data:
            _LOGGER.info(f"{self.file_name}: No segments data found.")
            return room_id, img_np_array

        if segment_data:
            _LOGGER.info(f"{self.file_name}: Drawing segments.")
            for pixels in segment_data:
                room_color = self.img_h.shared.rooms_colors[room_id]
                rooms_list.append(room_color)
                _LOGGER.debug(
                    f"Room {room_id} color: {room_color}, "
                    f"{tuple(self.img_h.active_zones)}"
                )
                if (
                    self.img_h.active_zones
                    and len(self.img_h.active_zones) > room_id
                    and self.img_h.active_zones[room_id] == 1
                ):
                    room_color = (
                        ((2 * room_color[0]) + color_zone_clean[0]) // 3,
                        ((2 * room_color[1]) + color_zone_clean[1]) // 3,
                        ((2 * room_color[2]) + color_zone_clean[2]) // 3,
                        ((2 * room_color[3]) + color_zone_clean[3]) // 3,
                    )
                img_np_array = await self.draw.from_json_to_image(
                    img_np_array, pixels, pixel_size, room_color
                )
                room_id += 1
                if room_id > 15:
                    room_id = 0
        return room_id, img_np_array

    async def _draw_walls(
        self,
        img_np_array,
        walls_data,
        size_x,
        size_y,
        pos_top,
        pos_left,
        pixel_size,
        color_wall,
    ):
        """Draw the walls onto the image."""
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
        return img_np_array

    async def async_draw_charger(
        self,
        np_array: NumpyArray,
        m_json: JsonType,
        color_charger: Color,
    ) -> (NumpyArray, dict):
        """Get the charger position from the entity data."""
        try:
            charger_pos = self.data.rrm_coordinates_to_valetudo(
                self.data.get_rrm_charger_position(m_json)
            )
        except Exception as e:
            _LOGGER.warning(f"{self.file_name}: No charger position found. {e}")
        else:
            _LOGGER.debug("charger position: %s", charger_pos)
            if charger_pos:
                charger_pos_dictionary = {
                    "x": (charger_pos[0] * 10),
                    "y": (charger_pos[1] * 10),
                }

                np_array = await self.draw.battery_charger(
                    np_array, charger_pos[0], charger_pos[1], color_charger
                )
                return np_array, charger_pos_dictionary
            else:
                return np_array, {}

    async def async_draw_zones(
        self,
        m_json: JsonType,
        np_array: NumpyArray,
        color_zone_clean: Color,
    ) -> NumpyArray:
        """Get the zone clean from the JSON data."""
        try:
            zone_clean = self.data.get_rrm_currently_cleaned_zones(m_json)
        except (ValueError, KeyError):
            zone_clean = None
        else:
            _LOGGER.info(f"{self.file_name}: Got zones.")
        if zone_clean:
            if zone_clean:
                np_array = await self.draw.zones(np_array, zone_clean, color_zone_clean)
            return np_array
        else:
            return np_array

    async def async_draw_virtual_restrictions(
        self, m_json: JsonType, np_array: NumpyArray, color_no_go: Color
    ) -> NumpyArray:
        """Get the virtual walls from the JSON data."""
        try:
            virtual_walls = self.data.get_rrm_virtual_walls(m_json)
        except (ValueError, KeyError):
            virtual_walls = None
        else:
            _LOGGER.info(f"{self.file_name}: Got virtual walls.")
        if virtual_walls:
            np_array = await self.draw.draw_virtual_walls(
                np_array, virtual_walls, color_no_go
            )
        try:
            no_go_area = self.data.get_rrm_forbidden_zones(m_json)
        except KeyError:
            no_go_area = None
        if no_go_area:
            np_array = await self.draw.zones(np_array, no_go_area, color_no_go)
        return np_array

    async def async_draw_path(
        self,
        np_array: NumpyArray,
        m_json: JsonType,
        color_move: Color,
    ) -> NumpyArray:
        """Get the paths from the JSON data."""
        # Initialize the variables
        path_pixel_formatted = None
        # Extract the paths data from the JSON data.
        try:
            path_pixel = self.data.get_rrm_path(m_json)
            path_pixel_formatted = self.data.sublist_join(
                self.data.rrm_valetudo_path_array(path_pixel["points"]), 2
            )
        except KeyError as e:
            _LOGGER.warning(f"{self.file_name}: Error extracting paths data: {str(e)}")
        finally:
            if path_pixel_formatted:
                np_array = await self.draw.lines(
                    np_array, path_pixel_formatted, 5, color_move
                )
        return np_array

    async def async_get_entity_data(self, m_json: JsonType) -> dict or None:
        """Get the entity data from the JSON data."""
        try:
            entity_dict = self.data.find_points_entities(m_json)
        except (ValueError, KeyError):
            entity_dict = None
        else:
            _LOGGER.info(f"{self.file_name}: Got the points in the json.")
        return entity_dict

    @staticmethod
    async def async_copy_array(original_array: NumpyArray) -> NumpyArray:
        """Copy the array."""
        return NumpyArray.copy(original_array)

    async def calculate_array_hash(self, layers: dict, active: list[int] = None) -> str:
        """Calculate the hash of the image based on the layers and active segments walls."""
        self.img_h.active_zones = active
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

    async def async_get_robot_position(self, m_json: JsonType) -> tuple | None:
        """Get the robot position from the entity data."""
        robot_pos = None
        robot_position = None
        angle = [0, 0]
        try:
            robot_pos_data = self.data.get_rrm_robot_position(m_json)
            robot_pos = self.data.rrm_coordinates_to_valetudo(robot_pos_data)
            angle = self.data.get_rrm_robot_angle(m_json)
        except (ValueError, KeyError):
            _LOGGER.warning(f"{self.file_name} No robot position found.")
            return None, None, None
        finally:
            robot_position_angle = round(angle[0], 0)
            if robot_pos and robot_position_angle:
                robot_position = robot_pos
                _LOGGER.debug(
                    f"robot position: {robot_pos}, robot angle: {robot_position_angle}"
                )
                if self.img_h.rooms_pos is None:
                    self.img_h.robot_pos = {
                        "x": robot_position[0] * 10,
                        "y": robot_position[1] * 10,
                        "angle": robot_position_angle,
                    }
                else:
                    self.img_h.robot_pos = await self.img_h.async_get_robot_in_room(
                        (robot_position[0] * 10),
                        (robot_position[1] * 10),
                        robot_position_angle,
                    )
        return robot_pos, robot_position, robot_position_angle

    async def async_draw_robot_on_map(
        self,
        np_array: NumpyArray,
        robot_pos: tuple,
        robot_angle: float,
        color_robot: Color,
    ) -> NumpyArray:
        """Draw the robot on the map."""
        if robot_pos and robot_angle:
            np_array = await self.draw.robot(
                np_array,
                robot_pos[0],
                robot_pos[1],
                robot_angle,
                color_robot,
                self.img_h.file_name,
            )
        return np_array

"""
Image Draw Class for Valetudo Hypfer Image Handling.
This class is used to simplify the ImageHandler class.
Version: 2024.07.2
"""

from __future__ import annotations

import hashlib
import json
import logging

from custom_components.mqtt_vacuum_camera.types import (
    Color,
    JsonType,
    NumpyArray,
    RobotPosition,
)

_LOGGER = logging.getLogger(__name__)


class ImageDraw:
    """Class to handle the image creation."""

    """It Draws each elements of the images, like the walls, zones, paths, etc."""

    def __init__(self, image_handler):
        self.img_h = image_handler
        self.file_name = self.img_h.shared.file_name

    async def draw_go_to_flag(
        self, np_array: NumpyArray, entity_dict: dict, color_go_to: Color
    ) -> NumpyArray:
        """Draw the goto target flag on the map."""
        go_to = entity_dict.get("go_to_target")
        if go_to:
            np_array = await self.img_h.draw.go_to_flag(
                np_array,
                (go_to[0]["points"][0], go_to[0]["points"][1]),
                self.img_h.shared.image_rotate,
                color_go_to,
            )
            return np_array
        else:
            return np_array

    async def async_draw_base_layer(
        self,
        img_np_array,
        compressed_pixels_list,
        layer_type,
        color_wall,
        color_zone_clean,
        pixel_size,
    ):
        """Draw the base layer of the map."""
        room_id = 0
        for compressed_pixels in compressed_pixels_list:
            pixels = self.img_h.data.sublist(compressed_pixels, 3)
            if layer_type == "segment" or layer_type == "floor":
                room_color = self.img_h.shared.rooms_colors[room_id]
                try:
                    if layer_type == "segment":
                        # Check if the room is active and set a modified color
                        if self.img_h.active_zones and (
                            room_id in range(len(self.img_h.active_zones))
                        ):
                            if self.img_h.active_zones[room_id] == 1:
                                room_color = (
                                    ((2 * room_color[0]) + color_zone_clean[0]) // 3,
                                    ((2 * room_color[1]) + color_zone_clean[1]) // 3,
                                    ((2 * room_color[2]) + color_zone_clean[2]) // 3,
                                    ((2 * room_color[3]) + color_zone_clean[3]) // 3,
                                )
                except IndexError as e:
                    _LOGGER.warning(f"{self.file_name} Image Draw Error: {e}")
                    _LOGGER.debug(
                        f"{self.file_name} Active Zones: {self.img_h.active_zones} and Room ID: {room_id}"
                    )
                finally:
                    img_np_array = await self.img_h.draw.from_json_to_image(
                        img_np_array, pixels, pixel_size, room_color
                    )
                    if room_id < 15:
                        room_id += 1
                    else:
                        room_id = 0
            elif layer_type == "wall":
                # Drawing walls.
                img_np_array = await self.img_h.draw.from_json_to_image(
                    img_np_array, pixels, pixel_size, color_wall
                )
        return room_id, img_np_array

    async def async_draw_obstacle(
        self, np_array: NumpyArray, entity_dict: dict, color_no_go: Color
    ) -> NumpyArray:
        """Get the obstacle positions from the entity data."""
        try:
            obstacle_data = entity_dict.get("obstacle")
        except KeyError:
            _LOGGER.info(f"{self.file_name} No obstacle found.")
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
            # and draw obstacles on the map
            if obstacle_positions:
                self.img_h.draw.draw_obstacles(
                    np_array, obstacle_positions, color_no_go
                )
                _LOGGER.debug(
                    f"{self.file_name} All obstacle positions: %s",
                    obstacle_positions,
                )
                return np_array
            else:
                return np_array

    async def async_draw_charger(
        self,
        np_array: NumpyArray,
        entity_dict: dict,
        color_charger: Color,
    ) -> NumpyArray:
        """Get the charger position from the entity data."""
        try:
            charger_pos = entity_dict.get("charger_location")
        except KeyError:
            _LOGGER.warning(f"{self.file_name}: No charger position found.")
        else:
            if charger_pos:
                charger_pos = charger_pos[0]["points"]
                self.img_h.charger_pos = {
                    "x": charger_pos[0],
                    "y": charger_pos[1],
                }
                np_array = await self.img_h.draw.battery_charger(
                    np_array, charger_pos[0], charger_pos[1], color_charger
                )
                return np_array
            else:
                return np_array

    async def async_get_json_id(self, my_json: JsonType) -> str | None:
        """Return the JSON ID from the image."""
        try:
            json_id = my_json["metaData"]["nonce"]
        except (ValueError, KeyError) as e:
            _LOGGER.debug(f"{self.file_name}: No JsonID provided: {e}")
            json_id = None
        return json_id

    async def async_draw_zones(
        self,
        m_json: JsonType,
        np_array: NumpyArray,
        color_zone_clean: Color,
        color_no_go: Color,
    ) -> NumpyArray:
        """Get the zone clean from the JSON data."""
        try:
            zone_clean = self.img_h.data.find_zone_entities(m_json)
        except (ValueError, KeyError):
            zone_clean = None
        else:
            _LOGGER.info(f"{self.file_name}: Got zones.")
        if zone_clean:
            try:
                zones_active = zone_clean.get("active_zone")
            except KeyError:
                zones_active = None
            if zones_active:
                np_array = await self.img_h.draw.zones(
                    np_array, zones_active, color_zone_clean
                )
            try:
                no_go_zones = zone_clean.get("no_go_area")
            except KeyError:
                no_go_zones = None

            try:
                no_mop_zones = zone_clean.get("no_mop_area")
            except KeyError:
                no_mop_zones = None

            if no_go_zones:
                np_array = await self.img_h.draw.zones(
                    np_array, no_go_zones, color_no_go
                )
            if no_mop_zones:
                np_array = await self.img_h.draw.zones(
                    np_array, no_mop_zones, color_no_go
                )
            return np_array
        else:
            return np_array

    async def async_draw_virtual_walls(
        self, m_json: JsonType, np_array: NumpyArray, color_no_go: Color
    ) -> NumpyArray:
        """Get the virtual walls from the JSON data."""
        try:
            virtual_walls = self.img_h.data.find_virtual_walls(m_json)
        except (ValueError, KeyError):
            virtual_walls = None
        else:
            _LOGGER.info(f"{self.file_name}: Got virtual walls.")
        if virtual_walls:
            np_array = await self.img_h.draw.draw_virtual_walls(
                np_array, virtual_walls, color_no_go
            )
            return np_array
        else:
            return np_array

    async def async_draw_paths(
        self,
        np_array: NumpyArray,
        m_json: JsonType,
        color_move: Color,
        color_gray: Color,
    ) -> NumpyArray:
        """Get the paths from the JSON data."""
        # Initialize the variables
        path_pixels = None
        predicted_path = None
        # Extract the paths data from the JSON data.
        try:
            paths_data = self.img_h.data.find_paths_entities(m_json)
            predicted_path = paths_data.get("predicted_path", [])
            path_pixels = paths_data.get("path", [])
        except KeyError as e:
            _LOGGER.warning(f"{self.file_name}: Error extracting paths data: {str(e)}")
        finally:
            if predicted_path:
                predicted_path = predicted_path[0]["points"]
                predicted_path = self.img_h.data.sublist(predicted_path, 2)
                predicted_pat2 = self.img_h.data.sublist_join(predicted_path, 2)
                np_array = await self.img_h.draw.lines(
                    np_array, predicted_pat2, 2, color_gray
                )
        if path_pixels:
            for path in path_pixels:
                # Get the points from the current path and extend multiple paths.
                points = path.get("points", [])
                sublists = self.img_h.data.sublist(points, 2)
                self.img_h.shared.map_new_path = self.img_h.data.sublist_join(
                    sublists, 2
                )
                np_array = await self.img_h.draw.lines(
                    np_array, self.img_h.shared.map_new_path, 5, color_move
                )
            return np_array
        else:
            return np_array

    async def async_get_entity_data(self, m_json: JsonType) -> dict or None:
        """Get the entity data from the JSON data."""
        try:
            entity_dict = self.img_h.data.find_points_entities(m_json)
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

    async def async_get_robot_in_room(
        self, robot_y: int = 0, robot_x: int = 0, angle: float = 0.0
    ) -> RobotPosition:
        """Get the robot position and return in what room is."""
        if self.img_h.robot_in_room:
            # Check if the robot coordinates are inside the room's corners
            if (
                (self.img_h.robot_in_room["right"] >= int(robot_x))
                and (self.img_h.robot_in_room["left"] <= int(robot_x))
            ) and (
                (self.img_h.robot_in_room["down"] >= int(robot_y))
                and (self.img_h.robot_in_room["up"] <= int(robot_y))
            ):
                temp = {
                    "x": robot_x,
                    "y": robot_y,
                    "angle": angle,
                    "in_room": self.img_h.robot_in_room["room"],
                }
                if self.img_h.active_zones and (
                    self.img_h.robot_in_room["id"]
                    in range(len(self.img_h.active_zones))
                ):  # issue #100 Index out of range.
                    self.img_h.zooming = bool(
                        self.img_h.active_zones[self.img_h.robot_in_room["id"]]
                    )
                else:
                    self.img_h.zooming = False
                return temp
        # else we need to search and use the async method.
        if self.img_h.rooms_pos:
            last_room = None
            room_count = 0
            if self.img_h.robot_in_room:
                last_room = self.img_h.robot_in_room
            for room in self.img_h.rooms_pos:
                corners = room["corners"]
                self.img_h.robot_in_room = {
                    "id": room_count,
                    "left": int(corners[0][0]),
                    "right": int(corners[2][0]),
                    "up": int(corners[0][1]),
                    "down": int(corners[2][1]),
                    "room": str(room["name"]),
                }
                room_count += 1
                # Check if the robot coordinates are inside the room's corners
                if (
                    (self.img_h.robot_in_room["right"] >= int(robot_x))
                    and (self.img_h.robot_in_room["left"] <= int(robot_x))
                ) and (
                    (self.img_h.robot_in_room["down"] >= int(robot_y))
                    and (self.img_h.robot_in_room["up"] <= int(robot_y))
                ):
                    temp = {
                        "x": robot_x,
                        "y": robot_y,
                        "angle": angle,
                        "in_room": self.img_h.robot_in_room["room"],
                    }
                    _LOGGER.debug(
                        f"{self.file_name} is in {self.img_h.robot_in_room['room']}"
                    )
                    del room, corners, robot_x, robot_y  # free memory.
                    return temp
            del room, corners  # free memory.
            _LOGGER.debug(
                f"{self.file_name} not located within Camera Rooms coordinates."
            )
            self.img_h.robot_in_room = last_room
            self.img_h.zooming = False
            temp = {
                "x": robot_x,
                "y": robot_y,
                "angle": angle,
                "in_room": last_room["room"] if last_room else None,
            }
            # If the robot is not inside any room, return a default value
            return temp

    async def async_get_robot_position(self, entity_dict: dict) -> tuple | None:
        """Get the robot position from the entity data."""
        robot_pos = None
        robot_position = None
        robot_position_angle = None
        try:
            robot_pos = entity_dict.get("robot_position")
        except KeyError:
            _LOGGER.warning(f"{self.file_name} No robot position found.")
            return None, None, None
        finally:
            if robot_pos:
                robot_position = robot_pos[0]["points"]
                robot_position_angle = round(
                    float(robot_pos[0]["metaData"]["angle"]), 1
                )
                if self.img_h.rooms_pos is None:
                    self.img_h.robot_pos = {
                        "x": robot_position[0],
                        "y": robot_position[1],
                        "angle": robot_position_angle,
                    }
                else:
                    self.img_h.robot_pos = await self.async_get_robot_in_room(
                        robot_y=(robot_position[1]),
                        robot_x=(robot_position[0]),
                        angle=robot_position_angle,
                    )

        return robot_pos, robot_position, robot_position_angle

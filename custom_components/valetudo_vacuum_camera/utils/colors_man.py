"""
Colors RGBA
Version: v2024.05
"""

import logging

from custom_components.valetudo_vacuum_camera.const import (
    ALPHA_BACKGROUND,
    ALPHA_CHARGER,
    ALPHA_GO_TO,
    ALPHA_MOVE,
    ALPHA_NO_GO,
    ALPHA_ROBOT,
    ALPHA_ROOM_0,
    ALPHA_ROOM_1,
    ALPHA_ROOM_2,
    ALPHA_ROOM_3,
    ALPHA_ROOM_4,
    ALPHA_ROOM_5,
    ALPHA_ROOM_6,
    ALPHA_ROOM_7,
    ALPHA_ROOM_8,
    ALPHA_ROOM_9,
    ALPHA_ROOM_10,
    ALPHA_ROOM_11,
    ALPHA_ROOM_12,
    ALPHA_ROOM_13,
    ALPHA_ROOM_14,
    ALPHA_ROOM_15,
    ALPHA_TEXT,
    ALPHA_WALL,
    ALPHA_ZONE_CLEAN,
    COLOR_BACKGROUND,
    COLOR_CHARGER,
    COLOR_GO_TO,
    COLOR_MOVE,
    COLOR_NO_GO,
    COLOR_ROBOT,
    COLOR_ROOM_0,
    COLOR_ROOM_1,
    COLOR_ROOM_2,
    COLOR_ROOM_3,
    COLOR_ROOM_4,
    COLOR_ROOM_5,
    COLOR_ROOM_6,
    COLOR_ROOM_7,
    COLOR_ROOM_8,
    COLOR_ROOM_9,
    COLOR_ROOM_10,
    COLOR_ROOM_11,
    COLOR_ROOM_12,
    COLOR_ROOM_13,
    COLOR_ROOM_14,
    COLOR_ROOM_15,
    COLOR_TEXT,
    COLOR_WALL,
    COLOR_ZONE_CLEAN,
)

_LOGGER = logging.getLogger(__name__)

color_transparent = (0, 0, 0, 0)
color_charger = (0, 128, 0, 255)
color_move = (238, 247, 255, 255)
color_robot = (255, 255, 204, 255)
color_no_go = (255, 0, 0, 255)
color_go_to = (0, 255, 0, 255)
color_background = (0, 125, 255, 255)
color_zone_clean = (255, 255, 255, 25)
color_wall = (255, 255, 0, 255)
color_text = (255, 255, 255, 255)
color_grey = (125, 125, 125, 255)
color_black = (0, 0, 0, 255)
color_room_0 = (135, 206, 250, 255)
color_room_1 = (176, 226, 255, 255)
color_room_2 = (164, 211, 238, 255)
color_room_3 = (141, 182, 205, 255)
color_room_4 = (96, 123, 139, 255)
color_room_5 = (224, 255, 255, 255)
color_room_6 = (209, 238, 238, 255)
color_room_7 = (180, 205, 205, 255)
color_room_8 = (122, 139, 139, 255)
color_room_9 = (175, 238, 238, 255)
color_room_10 = (84, 153, 199, 255)
color_room_11 = (133, 193, 233, 255)
color_room_12 = (245, 176, 65, 255)
color_room_13 = (82, 190, 128, 255)
color_room_14 = (72, 201, 176, 255)
color_room_15 = (165, 105, 18, 255)

rooms_color = [
    color_room_0,
    color_room_1,
    color_room_2,
    color_room_3,
    color_room_4,
    color_room_5,
    color_room_6,
    color_room_7,
    color_room_8,
    color_room_9,
    color_room_10,
    color_room_11,
    color_room_12,
    color_room_13,
    color_room_14,
    color_room_15,
]

base_colors_array = [
    color_wall,
    color_zone_clean,
    color_robot,
    color_background,
    color_move,
    color_charger,
    color_no_go,
    color_go_to,
    color_text,
]

color_array = [
    base_colors_array[0],
    base_colors_array[6],  # color_no_go
    base_colors_array[7],  # color_go_to
    color_black,
    base_colors_array[2],  # color_robot
    base_colors_array[5],  # color_charger
    color_text,
    base_colors_array[4],  # color_move
    base_colors_array[3],  # color_background
    base_colors_array[1],  # color_zone_clean
    color_transparent,
    rooms_color,
]


class ColorsManagment:
    """Class to manage the colors.
    Imports and updates the colors from the user configuration."""

    def __init__(self, shared_var):
        self.shared_var = shared_var

    @staticmethod
    def add_alpha_to_rgb(alpha_channels, rgb_colors):
        """
        Add alpha channel to RGB colors using corresponding alpha channels.

        Args:
            alpha_channels (List[Optional[float]]): List of alpha channel values (0.0-255.0).
            rgb_colors (List[Tuple[int, int, int]]): List of RGB colors.

        Returns:
            List[Tuple[int, int, int, int]]: List of RGBA colors with alpha channel added.
        """
        if len(alpha_channels) != len(rgb_colors):
            _LOGGER.error("Input lists must have the same length.")
            return []

        result = []
        for alpha, rgb in zip(alpha_channels, rgb_colors):
            try:
                alpha_int = int(alpha)
                if alpha_int < 0:
                    alpha_int = 0
                elif alpha_int > 255:
                    alpha_int = 255

                if rgb is None:
                    result.append((0, 0, 0, alpha_int))
                else:
                    result.append((rgb[0], rgb[1], rgb[2], alpha_int))
            except (ValueError, TypeError):
                result.append(None)

        return result

    def set_initial_colours(self, device_info: dict) -> None:
        """Set the initial colours for the map."""
        try:
            user_colors = [
                device_info.get(COLOR_WALL),
                device_info.get(COLOR_ZONE_CLEAN),
                device_info.get(COLOR_ROBOT),
                device_info.get(COLOR_BACKGROUND),
                device_info.get(COLOR_MOVE),
                device_info.get(COLOR_CHARGER),
                device_info.get(COLOR_NO_GO),
                device_info.get(COLOR_GO_TO),
                device_info.get(COLOR_TEXT),
            ]
            user_alpha = [
                device_info.get(ALPHA_WALL),
                device_info.get(ALPHA_ZONE_CLEAN),
                device_info.get(ALPHA_ROBOT),
                device_info.get(ALPHA_BACKGROUND),
                device_info.get(ALPHA_MOVE),
                device_info.get(ALPHA_CHARGER),
                device_info.get(ALPHA_NO_GO),
                device_info.get(ALPHA_GO_TO),
                device_info.get(ALPHA_TEXT),
            ]
            rooms_colors = [
                device_info.get(COLOR_ROOM_0),
                device_info.get(COLOR_ROOM_1),
                device_info.get(COLOR_ROOM_2),
                device_info.get(COLOR_ROOM_3),
                device_info.get(COLOR_ROOM_4),
                device_info.get(COLOR_ROOM_5),
                device_info.get(COLOR_ROOM_6),
                device_info.get(COLOR_ROOM_7),
                device_info.get(COLOR_ROOM_8),
                device_info.get(COLOR_ROOM_9),
                device_info.get(COLOR_ROOM_10),
                device_info.get(COLOR_ROOM_11),
                device_info.get(COLOR_ROOM_12),
                device_info.get(COLOR_ROOM_13),
                device_info.get(COLOR_ROOM_14),
                device_info.get(COLOR_ROOM_15),
            ]
            rooms_alpha = [
                device_info.get(ALPHA_ROOM_0),
                device_info.get(ALPHA_ROOM_1),
                device_info.get(ALPHA_ROOM_2),
                device_info.get(ALPHA_ROOM_3),
                device_info.get(ALPHA_ROOM_4),
                device_info.get(ALPHA_ROOM_5),
                device_info.get(ALPHA_ROOM_6),
                device_info.get(ALPHA_ROOM_7),
                device_info.get(ALPHA_ROOM_8),
                device_info.get(ALPHA_ROOM_9),
                device_info.get(ALPHA_ROOM_10),
                device_info.get(ALPHA_ROOM_11),
                device_info.get(ALPHA_ROOM_12),
                device_info.get(ALPHA_ROOM_13),
                device_info.get(ALPHA_ROOM_14),
                device_info.get(ALPHA_ROOM_15),
            ]
            self.shared_var.update_user_colors(
                self.add_alpha_to_rgb(user_alpha, user_colors)
            )
            self.shared_var.update_rooms_colors(
                self.add_alpha_to_rgb(rooms_alpha, rooms_colors)
            )
        except (ValueError, IndexError, UnboundLocalError) as e:
            _LOGGER.error("Error while populating colors: %s", e)

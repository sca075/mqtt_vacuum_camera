"""Colors RGBA Version 1.4.3"""

import logging

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

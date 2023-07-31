"""Colors RGBA Version 1.1.8"""

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
color_white = (255, 255, 255, 255)
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
]

color_array = [
    base_colors_array[0],
    base_colors_array[6],  # color_no_go
    base_colors_array[7],  # color_go_to
    color_black,
    base_colors_array[2],  # color_robot
    base_colors_array[5],  # color_charger
    color_white,
    base_colors_array[4],  # color_move
    base_colors_array[3],  # color_background
    base_colors_array[1],  # color_zone_clean
    color_transparent,
    rooms_color,
]

def add_alpha_to_rgb(rgb_colors, rgba_colors):
    """
    Add alpha channel to RGB colors using corresponding RGBA colors.

    Args:
        rgb_colors (List[Tuple[int, int, int]]): List of RGB colors.
        rgba_colors (List[Tuple[int, int, int, int]]): List of RGBA colors.

    Returns:
        List[Tuple[int, int, int, int]]: List of RGBA colors with alpha channel added.
    """
    if len(rgb_colors) != len(rgba_colors):
        raise ValueError("Input lists must have the same length.")

    result = []
    for rgb, rgba in zip(rgb_colors, rgba_colors):
        if len(rgb) != 3 or len(rgba) != 4:
            raise ValueError("RGB and RGBA colors must be tuples of length 3 and 4, respectively.")
        result.append((*rgb, rgba[3]))  # Append RGB with the alpha channel from RGBA

    return result


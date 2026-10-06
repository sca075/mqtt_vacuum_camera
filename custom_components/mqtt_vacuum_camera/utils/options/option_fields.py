"""
Field mappings between the options flow forms and the stored camera options.
Each mapping is {stored option key: form field key}.
"""

from typing import Any, Dict, Iterable, Mapping, Optional

from ...const import (
    ALPHA_BACKGROUND,
    ALPHA_CARPET,
    ALPHA_CHARGER,
    ALPHA_GO_TO,
    ALPHA_MATERIAL_TILE,
    ALPHA_MATERIAL_WOOD,
    ALPHA_MOP_MOVE,
    ALPHA_MOVE,
    ALPHA_NO_GO,
    ALPHA_ROBOT,
    ALPHA_ROOM_0,
    ALPHA_TEXT,
    ALPHA_WALL,
    ALPHA_ZONE_CLEAN,
    ATTR_MARGINS,
    ATTR_ROTATE,
    COLOR_BACKGROUND,
    COLOR_CARPET,
    COLOR_CHARGER,
    COLOR_GO_TO,
    COLOR_MATERIAL_TILE,
    COLOR_MATERIAL_WOOD,
    COLOR_MOP_MOVE,
    COLOR_MOVE,
    COLOR_NO_GO,
    COLOR_ROBOT,
    COLOR_ROOM_0,
    COLOR_TEXT,
    COLOR_WALL,
    COLOR_ZONE_CLEAN,
    CONF_ASPECT_RATIO,
    CONF_AUTO_ZOOM,
    CONF_DEF_CONTEXT_TYPE,
    CONF_DISABLE_CARPETS,
    CONF_DISABLE_MATERIAL_OVERLAY,
    CONF_MOP_PATH_WIDTH,
    CONF_OBSTACLE_LINK_IP,
    CONF_OBSTACLE_LINK_PORT,
    CONF_OBSTACLE_LINK_PROTOCOL,
    CONF_ROBOT_SIZE,
    CONF_VAC_STAT,
    CONF_VAC_STAT_FONT,
    CONF_VAC_STAT_POS,
    CONF_VAC_STAT_SIZE,
    CONF_ZOOM_LOCK_RATIO,
)

MATERIALS_FIELDS = {
    "disable_material_overlay": CONF_DISABLE_MATERIAL_OVERLAY,
    "disable_carpets": CONF_DISABLE_CARPETS,
    "color_carpet": COLOR_CARPET,
    "color_material_wood": COLOR_MATERIAL_WOOD,
    "color_material_tile": COLOR_MATERIAL_TILE,
    "alpha_carpet": ALPHA_CARPET,
    "alpha_material_wood": ALPHA_MATERIAL_WOOD,
    "alpha_material_tile": ALPHA_MATERIAL_TILE,
}

IMAGE_BASIC_FIELDS = {
    "rotate_image": ATTR_ROTATE,
    "margins": ATTR_MARGINS,
    "aspect_ratio": CONF_ASPECT_RATIO,
    "zoom_lock_ratio": CONF_ZOOM_LOCK_RATIO,
    "auto_zoom": CONF_AUTO_ZOOM,
    "robot_size": CONF_ROBOT_SIZE,
    "mop_path_width": CONF_MOP_PATH_WIDTH,
    "def_context_type": CONF_DEF_CONTEXT_TYPE,
}

STATUS_TEXT_FIELDS = {
    "show_vac_status": CONF_VAC_STAT,
    "vac_status_font": CONF_VAC_STAT_FONT,
    "vac_status_size": CONF_VAC_STAT_SIZE,
    "vac_status_position": CONF_VAC_STAT_POS,
    "color_text": COLOR_TEXT,
}

OBSTACLE_LINK_FIELDS = {
    CONF_OBSTACLE_LINK_PROTOCOL: CONF_OBSTACLE_LINK_PROTOCOL,
    CONF_OBSTACLE_LINK_PORT: CONF_OBSTACLE_LINK_PORT,
    CONF_OBSTACLE_LINK_IP: CONF_OBSTACLE_LINK_IP,
}

BASE_COLOURS_FIELDS = {
    "color_charger": COLOR_CHARGER,
    "color_move": COLOR_MOVE,
    "color_mop_move": COLOR_MOP_MOVE,
    "color_wall": COLOR_WALL,
    "color_robot": COLOR_ROBOT,
    "color_go_to": COLOR_GO_TO,
    "color_no_go": COLOR_NO_GO,
    "color_zone_clean": COLOR_ZONE_CLEAN,
    "color_background": COLOR_BACKGROUND,
}

BASE_ALPHA_FIELDS = {
    "alpha_charger": ALPHA_CHARGER,
    "alpha_move": ALPHA_MOVE,
    "alpha_mop_move": ALPHA_MOP_MOVE,
    "alpha_wall": ALPHA_WALL,
    "alpha_robot": ALPHA_ROBOT,
    "alpha_go_to": ALPHA_GO_TO,
    "alpha_no_go": ALPHA_NO_GO,
    "alpha_zone_clean": ALPHA_ZONE_CLEAN,
    "alpha_background": ALPHA_BACKGROUND,
    "alpha_text": ALPHA_TEXT,
}

FLOOR_COLOUR_FIELDS = {"color_room_0": COLOR_ROOM_0}

FLOOR_ALPHA_FIELDS = {"alpha_room_0": ALPHA_ROOM_0}


def same_key_fields(keys: Iterable[str]) -> Dict[str, str]:
    """Build a mapping where the stored key and the form key are the same."""
    return {key: key for key in keys}


def room_fields(prefix: str, start: int, end: int) -> Dict[str, str]:
    """Build the mapping for rooms start..end-1, e.g. color_room_0, color_room_1."""
    return same_key_fields(f"{prefix}_{i}" for i in range(start, end))


def extract_options(
    user_input: Mapping[str, Any],
    fields: Mapping[str, str],
    default: Optional[Any] = None,
) -> Dict[str, Any]:
    """Return {option key: value} read from the form input.

    Fields missing from the input get the default value.
    """
    return {
        option_key: user_input.get(form_key, default)
        for option_key, form_key in fields.items()
    }

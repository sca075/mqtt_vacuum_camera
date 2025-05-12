"""Constants for the mqtt_vacuum_camera integration.
Last Updated on version: 2025.3.0b2
"""

from enum import Enum
import logging
from typing import Final

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN

# Required in Config_Flow
DOMAIN: Final = "mqtt_vacuum_camera"
DEFAULT_NAME: Final = "mqtt vacuum camera"
ICON: Final = "mdi:camera"
NAME: Final = "MQTT Vacuum Camera"

# Required in Coordinator and Services
CAMERA = CAMERA_DOMAIN
VACUUM = VACUUM_DOMAIN
SENSOR = SENSOR_DOMAIN

CAMERA_STORAGE = "valetudo_camera"
DEFAULT_ROOMS = 1  # 15 is the maximum number of rooms.
ATTR_ROTATE = "rotate_image"
ATTR_CROP = "crop_image"
ATTR_MARGINS = "margins"
CONF_OFFSET_TOP = "offset_top"
CONF_OFFSET_BOTTOM = "offset_bottom"
CONF_OFFSET_LEFT = "offset_left"
CONF_OFFSET_RIGHT = "offset_right"
CONF_ASPECT_RATIO = "aspect_ratio"
CONF_VAC_STAT = "show_vac_status"
CONF_VAC_STAT_SIZE = "vac_status_size"
CONF_VAC_STAT_POS = "vac_status_position"
CONF_VAC_STAT_FONT = "vac_status_font"
CONF_VACUUM_CONNECTION_STRING = "vacuum_map"
CONF_VACUUM_ENTITY_ID = "vacuum_entity"
CONF_VACUUM_CONFIG_ENTRY_ID = "vacuum_config_entry"
CONF_VACUUM_IDENTIFIERS = "vacuum_identifiers"
CONF_SNAPSHOTS_ENABLE = "enable_www_snapshots"
CONF_EXPORT_SVG = "get_svg_file"
CONF_AUTO_ZOOM = "auto_zoom"
CONF_ZOOM_LOCK_RATIO = "zoom_lock_ratio"
CONF_TRIMS_SAVE = "save_trims"
CONF_TRIMS_DATA = "trims_data"
CONF_FLOOR_NAME = "floor_name"
CONF_TRIM_UP = "trim_up"
CONF_TRIM_DOWN = "trim_down"
CONF_TRIM_LEFT = "trim_left"
CONF_TRIM_RIGHT = "trim_right"
CONF_TRIM_ACTION = "trim_action"

# Trim Actions
TRIM_ACTION_SAVE = "save"
TRIM_ACTION_RESET = "reset"
TRIM_ACTION_DELETE = "delete"

# Object visibility options
CONF_DISABLE_FLOOR = "disable_floor"
CONF_DISABLE_WALL = "disable_wall"
CONF_DISABLE_ROBOT = "disable_robot"
CONF_DISABLE_CHARGER = "disable_charger"
CONF_DISABLE_VIRTUAL_WALLS = "disable_virtual_walls"
CONF_DISABLE_RESTRICTED_AREAS = "disable_restricted_areas"
CONF_DISABLE_NO_MOP_AREAS = "disable_no_mop_areas"
CONF_DISABLE_OBSTACLES = "disable_obstacles"
CONF_DISABLE_PATH = "disable_path"
CONF_DISABLE_PREDICTED_PATH = "disable_predicted_path"
CONF_DISABLE_GO_TO_TARGET = "disable_go_to_target"

# List of all draw element flags for easier iteration
DRAW_FLAGS = [
    CONF_DISABLE_FLOOR,
    CONF_DISABLE_WALL,
    CONF_DISABLE_ROBOT,
    CONF_DISABLE_CHARGER,
    CONF_DISABLE_VIRTUAL_WALLS,
    CONF_DISABLE_RESTRICTED_AREAS,
    CONF_DISABLE_NO_MOP_AREAS,
    CONF_DISABLE_OBSTACLES,
    CONF_DISABLE_PATH,
    CONF_DISABLE_PREDICTED_PATH,
    CONF_DISABLE_GO_TO_TARGET,
]

# Room/Segment visibility options
CONF_DISABLE_ROOM_1 = "disable_room_1"
CONF_DISABLE_ROOM_2 = "disable_room_2"
CONF_DISABLE_ROOM_3 = "disable_room_3"
CONF_DISABLE_ROOM_4 = "disable_room_4"
CONF_DISABLE_ROOM_5 = "disable_room_5"
CONF_DISABLE_ROOM_6 = "disable_room_6"
CONF_DISABLE_ROOM_7 = "disable_room_7"
CONF_DISABLE_ROOM_8 = "disable_room_8"
CONF_DISABLE_ROOM_9 = "disable_room_9"
CONF_DISABLE_ROOM_10 = "disable_room_10"
CONF_DISABLE_ROOM_11 = "disable_room_11"
CONF_DISABLE_ROOM_12 = "disable_room_12"
CONF_DISABLE_ROOM_13 = "disable_room_13"
CONF_DISABLE_ROOM_14 = "disable_room_14"
CONF_DISABLE_ROOM_15 = "disable_room_15"

# List of all room visibility flags for easier iteration
ROOM_FLAGS = [
    CONF_DISABLE_ROOM_1,
    CONF_DISABLE_ROOM_2,
    CONF_DISABLE_ROOM_3,
    CONF_DISABLE_ROOM_4,
    CONF_DISABLE_ROOM_5,
    CONF_DISABLE_ROOM_6,
    CONF_DISABLE_ROOM_7,
    CONF_DISABLE_ROOM_8,
    CONF_DISABLE_ROOM_9,
    CONF_DISABLE_ROOM_10,
    CONF_DISABLE_ROOM_11,
    CONF_DISABLE_ROOM_12,
    CONF_DISABLE_ROOM_13,
    CONF_DISABLE_ROOM_14,
    CONF_DISABLE_ROOM_15,
]

LOGGER = logging.getLogger(__package__)

SENSOR_NO_DATA = {
    "mainBrush": 0,
    "sideBrush": 0,
    "filter": 0,
    "currentCleanTime": 0,
    "currentCleanArea": 0,
    "cleanTime": 0,
    "cleanArea": 0,
    "cleanCount": 0,
    "battery": 0,
    "state": 0,
    "last_run_start": 0,
    "last_run_end": 0,
    "last_run_duration": 0,
    "last_run_area": 0,
    "last_bin_out": 0,
    "last_bin_full": 0,
    "last_loaded_map": "NoMap",
    "robot_in_room": "Unsupported",
}

DEFAULT_VALUES = {
    "rotate_image": "0",
    "margins": "100",
    "aspect_ratio": "None",
    "offset_top": 0,
    "offset_bottom": 0,
    "offset_left": 0,
    "offset_right": 0,
    "auto_zoom": False,
    "zoom_lock_ratio": True,
    "show_vac_status": False,
    "vac_status_font": "custom_components/mqtt_vacuum_camera/utils/fonts/FiraSans.ttf",
    "vac_status_size": 50,
    "vac_status_position": True,
    "get_svg_file": False,
    "save_trims": True,
    "trims_data": {"trim_left": 0, "trim_up": 0, "trim_right": 0, "trim_down": 0},
    "enable_www_snapshots": False,
    "disable_floor": False,
    "disable_wall": False,
    "disable_robot": False,
    "disable_charger": False,
    "disable_virtual_walls": False,
    "disable_restricted_areas": False,
    "disable_no_mop_areas": False,
    "disable_obstacles": False,
    "disable_path": False,
    "disable_predicted_path": False,
    "disable_go_to_target": False,
    "disable_room_1": False,
    "disable_room_2": False,
    "disable_room_3": False,
    "disable_room_4": False,
    "disable_room_5": False,
    "disable_room_6": False,
    "disable_room_7": False,
    "disable_room_8": False,
    "disable_room_9": False,
    "disable_room_10": False,
    "disable_room_11": False,
    "disable_room_12": False,
    "disable_room_13": False,
    "disable_room_14": False,
    "disable_room_15": False,
    "color_charger": [255, 128, 0],
    "color_move": [238, 247, 255],
    "color_wall": [255, 255, 0],
    "color_robot": [255, 255, 204],
    "color_go_to": [0, 255, 0],
    "color_no_go": [255, 0, 0],
    "color_zone_clean": [255, 255, 255],
    "color_background": [0, 125, 255],
    "color_text": [255, 255, 255],
    "alpha_charger": 255.0,
    "alpha_move": 255.0,
    "alpha_wall": 255.0,
    "alpha_robot": 255.0,
    "alpha_go_to": 255.0,
    "alpha_no_go": 125.0,
    "alpha_zone_clean": 125.0,
    "alpha_background": 255.0,
    "alpha_text": 255.0,
    "color_room_0": [135, 206, 250],
    "color_room_1": [176, 226, 255],
    "color_room_2": [165, 105, 18],
    "color_room_3": [164, 211, 238],
    "color_room_4": [141, 182, 205],
    "color_room_5": [96, 123, 139],
    "color_room_6": [224, 255, 255],
    "color_room_7": [209, 238, 238],
    "color_room_8": [180, 205, 205],
    "color_room_9": [122, 139, 139],
    "color_room_10": [175, 238, 238],
    "color_room_11": [84, 153, 199],
    "color_room_12": [133, 193, 233],
    "color_room_13": [245, 176, 65],
    "color_room_14": [82, 190, 128],
    "color_room_15": [72, 201, 176],
    "alpha_room_0": 255.0,
    "alpha_room_1": 255.0,
    "alpha_room_2": 255.0,
    "alpha_room_3": 255.0,
    "alpha_room_4": 255.0,
    "alpha_room_5": 255.0,
    "alpha_room_6": 255.0,
    "alpha_room_7": 255.0,
    "alpha_room_8": 255.0,
    "alpha_room_9": 255.0,
    "alpha_room_10": 255.0,
    "alpha_room_11": 255.0,
    "alpha_room_12": 255.0,
    "alpha_room_13": 255.0,
    "alpha_room_14": 255.0,
    "alpha_room_15": 255.0,
}

KEYS_TO_UPDATE = [
    "rotate_image",
    "margins",
    "aspect_ratio",
    "offset_top",
    "offset_bottom",
    "offset_left",
    "offset_right",
    "trims_data",
    "auto_zoom",
    "zoom_lock_ratio",
    "show_vac_status",
    "vac_status_size",
    "vac_status_position",
    "vac_status_font",
    "get_svg_file",
    "enable_www_snapshots",
    "disable_floor",
    "disable_wall",
    "disable_robot",
    "disable_charger",
    "disable_virtual_walls",
    "disable_restricted_areas",
    "disable_no_mop_areas",
    "disable_obstacles",
    "disable_path",
    "disable_predicted_path",
    "disable_go_to_target",
    "disable_room_1",
    "disable_room_2",
    "disable_room_3",
    "disable_room_4",
    "disable_room_5",
    "disable_room_6",
    "disable_room_7",
    "disable_room_8",
    "disable_room_9",
    "disable_room_10",
    "disable_room_11",
    "disable_room_12",
    "disable_room_13",
    "disable_room_14",
    "disable_room_15",
    "color_charger",
    "color_move",
    "color_wall",
    "color_robot",
    "color_go_to",
    "color_no_go",
    "color_zone_clean",
    "color_background",
    "color_text",
    "alpha_charger",
    "alpha_move",
    "alpha_wall",
    "alpha_robot",
    "alpha_go_to",
    "alpha_no_go",
    "alpha_zone_clean",
    "alpha_background",
    "alpha_text",
    "color_room_0",
    "color_room_1",
    "color_room_2",
    "color_room_3",
    "color_room_4",
    "color_room_5",
    "color_room_6",
    "color_room_7",
    "color_room_8",
    "color_room_9",
    "color_room_10",
    "color_room_11",
    "color_room_12",
    "color_room_13",
    "color_room_14",
    "color_room_15",
    "alpha_room_0",
    "alpha_room_1",
    "alpha_room_2",
    "alpha_room_3",
    "alpha_room_4",
    "alpha_room_5",
    "alpha_room_6",
    "alpha_room_7",
    "alpha_room_8",
    "alpha_room_9",
    "alpha_room_10",
    "alpha_room_11",
    "alpha_room_12",
    "alpha_room_13",
    "alpha_room_14",
    "alpha_room_15",
]

ALPHA_VALUES = {
    "min": 0.0,  # Minimum value
    "max": 255.0,  # Maximum value
    "step": 1.0,  # Step value
}

TEXT_SIZE_VALUES = {
    "min": 5,  # Minimum value
    "max": 51,  # Maximum value
    "step": 1,  # Step value
}

ROTATION_VALUES = [
    {"label": "0", "value": "0"},
    {"label": "90", "value": "90"},
    {"label": "180", "value": "180"},
    {"label": "270", "value": "270"},
]

RATIO_VALUES = [
    {"label": "Original Ratio.", "value": "None"},
    {"label": "1:1", "value": "1, 1"},
    {"label": "2:1", "value": "2, 1"},
    {"label": "3:2", "value": "3, 2"},
    {"label": "5:4", "value": "5, 4"},
    {"label": "9:16", "value": "9, 16"},
    {"label": "16:9", "value": "16, 9"},
]

FONTS_AVAILABLE = [
    {
        "label": "Fira Sans",
        "value": "custom_components/mqtt_vacuum_camera/utils/fonts/FiraSans.ttf",
    },
    {
        "label": "Inter",
        "value": "custom_components/mqtt_vacuum_camera/utils/fonts/Inter-VF.ttf",
    },
    {
        "label": "M Plus Regular",
        "value": "custom_components/mqtt_vacuum_camera/utils/fonts/MPLUSRegular.ttf",
    },
    {
        "label": "Noto Sans CJKhk",
        "value": "custom_components/mqtt_vacuum_camera/utils/fonts/NotoSansCJKhk-VF.ttf",
    },
    {
        "label": "Noto Kufi Arabic",
        "value": "custom_components/mqtt_vacuum_camera/utils/fonts/NotoKufiArabic-VF.ttf",
    },
    {
        "label": "Noto Sans Khojki",
        "value": "custom_components/mqtt_vacuum_camera/utils/fonts/NotoSansKhojki.ttf",
    },
    {
        "label": "Lato Regular",
        "value": "custom_components/mqtt_vacuum_camera/utils/fonts/Lato-Regular.ttf",
    },
]

NOT_STREAMING_STATES = {
    "idle",
    "paused",
    "charging",
    "error",
    "docked",
}

DECODED_TOPICS = {
    "/MapData/segments",
    "/maploader/map",
    "/maploader/status",
    "/StatusStateAttribute/status",
    "/StatusStateAttribute/error_description",
    "/$state",
    "/BatteryStateAttribute/level",
    "/WifiConfigurationCapability/ips",
    "/state",  # Rand256
    "/destinations",  # Rand256
    "/command",  # Rand256
    "/custom_command",  # Rand256
    "/attributes",  # Rand256
}


# self.command_topic need to be added to this dictionary after init.
NON_DECODED_TOPICS = {
    "/MapData/map-data",
    "/map_data",
}

"""App Constants. Not in use, and dummy values"""
IDLE_SCAN_INTERVAL = 120
CLEANING_SCAN_INTERVAL = 5
IS_ALPHA = "add_base_alpha"
IS_ALPHA_R1 = "add_room_1_alpha"
IS_ALPHA_R2 = "add_room_2_alpha"
IS_OFFSET = "add_offset"

"""Base Colours RGB"""
COLOR_CHARGER = "color_charger"
COLOR_MOVE = "color_move"
COLOR_ROBOT = "color_robot"
COLOR_NO_GO = "color_no_go"
COLOR_GO_TO = "color_go_to"
COLOR_BACKGROUND = "color_background"
COLOR_ZONE_CLEAN = "color_zone_clean"
COLOR_WALL = "color_wall"
COLOR_TEXT = "color_text"

"Rooms Colours RGB"
COLOR_ROOM_0 = "color_room_0"
COLOR_ROOM_1 = "color_room_1"
COLOR_ROOM_2 = "color_room_2"
COLOR_ROOM_3 = "color_room_3"
COLOR_ROOM_4 = "color_room_4"
COLOR_ROOM_5 = "color_room_5"
COLOR_ROOM_6 = "color_room_6"
COLOR_ROOM_7 = "color_room_7"
COLOR_ROOM_8 = "color_room_8"
COLOR_ROOM_9 = "color_room_9"
COLOR_ROOM_10 = "color_room_10"
COLOR_ROOM_11 = "color_room_11"
COLOR_ROOM_12 = "color_room_12"
COLOR_ROOM_13 = "color_room_13"
COLOR_ROOM_14 = "color_room_14"
COLOR_ROOM_15 = "color_room_15"

"""Alpha for RGBA Colours"""
ALPHA_CHARGER = "alpha_charger"
ALPHA_MOVE = "alpha_move"
ALPHA_ROBOT = "alpha_robot"
ALPHA_NO_GO = "alpha_no_go"
ALPHA_GO_TO = "alpha_go_to"
ALPHA_BACKGROUND = "alpha_background"
ALPHA_ZONE_CLEAN = "alpha_zone_clean"
ALPHA_WALL = "alpha_wall"
ALPHA_TEXT = "alpha_text"
ALPHA_ROOM_0 = "alpha_room_0"
ALPHA_ROOM_1 = "alpha_room_1"
ALPHA_ROOM_2 = "alpha_room_2"
ALPHA_ROOM_3 = "alpha_room_3"
ALPHA_ROOM_4 = "alpha_room_4"
ALPHA_ROOM_5 = "alpha_room_5"
ALPHA_ROOM_6 = "alpha_room_6"
ALPHA_ROOM_7 = "alpha_room_7"
ALPHA_ROOM_8 = "alpha_room_8"
ALPHA_ROOM_9 = "alpha_room_9"
ALPHA_ROOM_10 = "alpha_room_10"
ALPHA_ROOM_11 = "alpha_room_11"
ALPHA_ROOM_12 = "alpha_room_12"
ALPHA_ROOM_13 = "alpha_room_13"
ALPHA_ROOM_14 = "alpha_room_14"
ALPHA_ROOM_15 = "alpha_room_15"

""" Constants for the attribute keys """
ATTR_FRIENDLY_NAME = "friendly_name"
ATTR_VACUUM_BATTERY = "vacuum_battery"
ATTR_VACUUM_POSITION = "vacuum_position"
ATTR_VACUUM_TOPIC = "vacuum_topic"
ATTR_VACUUM_STATUS = "vacuum_status"
ATTR_JSON_DATA = "json_data"
ATTR_VACUUM_JSON_ID = "vacuum_json_id"
ATTR_CALIBRATION_POINTS = "calibration_points"
ATTR_SNAPSHOT = "snapshot"
ATTR_SNAPSHOT_PATH = "snapshot_path"
ATTR_ROOMS = "rooms"
ATTR_ZONES = "zones"
ATTR_POINTS = "points"
ATTR_OBSTACLES = "obstacles"
ATTR_CAMERA_MODE = "camera_mode"


class CameraModes(str, Enum):
    """Constants for the camera modes"""

    MAP_VIEW = "map_view"
    OBSTACLE_VIEW = "obstacle_view"
    OBSTACLE_DOWNLOAD = "load_view"
    OBSTACLE_SEARCH = "search_view"
    CAMERA_STANDBY = "camera_standby"
    CAMERA_OFF = False
    CAMERA_ON = True

"""Constants for the valetudo_vacuum_camera integration."""
"""Version 1.3.2"""

"""Required in Config_Flow"""
PLATFORMS = ["camera"]
DOMAIN = "valetudo_vacuum_camera"
DEFAULT_NAME = "valetudo vacuum camera"
ATTR_ROTATE = "rotate_image"
ATTR_CROP = "crop_image"
ATTR_TRIM_TOP = "trim_top"
ATTR_TRIM_BOTTOM = "trim_bottom"
ATTR_TRIM_LEFT = "trim_left"
ATTR_TRIM_RIGHT = "trim_right"
CONF_VAC_STAT = "show_vac_status"
CONF_MQTT_PASS = "broker_password"
CONF_MQTT_USER = "broker_user"
CONF_VACUUM_CONNECTION_STRING = "vacuum_map"
CONF_VACUUM_ENTITY_ID = "vacuum_entity"
ICON = "mdi:camera"
NAME = "Valetudo Vacuum Camera"

"""App Constants"""
IDLE_SCAN_INTERVAL = 120
CLEANING_SCAN_INTERVAL = 5

COLOR_CHARGER = "color_charger"
COLOR_MOVE = "color_move"
COLOR_ROBOT = "color_robot"
COLOR_NO_GO = "color_no_go"
COLOR_GO_TO = "color_go_to"
COLOR_BACKGROUND = "color_background"
COLOR_ZONE_CLEAN = "color_zone_clean"
COLOR_WALL = "color_wall"
COLOR_TEXT = "color_text"
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

CONF_COLORS = [
    COLOR_WALL,
    COLOR_ZONE_CLEAN,
    COLOR_ROBOT,
    COLOR_BACKGROUND,
    COLOR_MOVE,
    COLOR_CHARGER,
    COLOR_NO_GO,
    COLOR_GO_TO,
]

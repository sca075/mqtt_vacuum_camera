"""Constants for the valetudo_vacuum_camera integration."""
"""Version 1.1.7"""

"""Required in Config_Flow"""
PLATFORMS = ["camera"]
DOMAIN = "valetudo_vacuum_camera"
DEFAULT_NAME = "valetudo vacuum camera"
ATT_ROTATE = "rotate_image"
ATT_CROP = "crop_image"
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

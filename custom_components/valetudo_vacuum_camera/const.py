"""Constants for the valetudo_vacuum_camera integration."""

"""Required in Config_Flow"""
PLATFORMS = ["camera"]
DOMAIN = "valetudo_vacuum_camera"
DEFAULT_NAME = "valetudo vacuum camera"
CONF_VACUUM_CONNECTION_STRING = "vacuum_map"
CONF_VACUUM_ENTITY_ID = "vacuum_entity"
ICON = "mdi:camera"

"""App Constants"""
IDLE_SCAN_INTERVAL = 120
CLEANING_SCAN_INTERVAL = 3

"""Colors"""
color_charger = (0, 128, 0, 255)
color_move = (238, 247, 255, 255)
color_robot = (255, 255, 204, 255)
color_wall = (255, 255, 0, 255)
color_white = (255, 255, 255, 255)
color_grey = (125, 125, 125, 255)
color_black = (0, 0, 0, 255)
color_ext_background = (125, 125, 125, 255)
color_home_background = (0, 255, 255, 255)
color_transparent = (0, 0, 0, 0)


#TODO Clean up when not required.
#SERVICE_CLEAN = "clean"
#SERVICE_GO_TO = "go_to"
#SERVICE_START_CLEANING = "start"
#SERVICE_STOP_CLEANING = "stop"
#SERVICE_ZONE_CLEANING = "zone_clean"

#ATTR_MAP = "map"
#ATTR_MAP_DATA = "map_data"
#ATTR_PATH = "path"
#ATTR_COORDINATES = "coordinates"
#ATTR_ROTATION = "rotation"
#ATTR_ZOOM = "zoom"
#ATTR_HOME_POSITION = "home_position"
#ATTR_CAMERA_ENTITY = "camera_entity"

EVENT_CAMERA_IMAGE_CAPTURED = "valetudo_camera_image_captured"

#CAMERA_IMAGE_TYPE_MAP = "map"
#CAMERA_IMAGE_TYPE_RAW_MAP = "raw_map"
#CAMERA_IMAGE_TYPE_LIVE = "live"

#CAMERA_IMAGE_TYPES = [
#    CAMERA_IMAGE_TYPE_MAP,
#    CAMERA_IMAGE_TYPE_RAW_MAP,
#    CAMERA_IMAGE_TYPE_LIVE,
#]


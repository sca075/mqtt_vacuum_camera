"""Constants for the valetudo_vacuum_camera integration."""

DOMAIN = "valetudo_vacuum_camera"
DEFAULT_NAME = "Valetudo Vacuum"
PLATFORMS = ["camera"]

ICON = "mdi:camera"

CONF_VACUUM_CONNECTION_STRING = "vacuum_map"
CONF_VACUUM_ENTITY_ID = "vacuum_entity"


#DEFAULT_SCAN_INTERVAL = 60
#IDLE_SCAN_INTERVAL = 120
#CLEANING_SCAN_INTERVAL = 5

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


STARTUP_MESSAGE = """
-------------------------------------------------------------------
Valetudo Camera has been installed.
Please restart Home Assistant to activate the integration.
-------------------------------------------------------------------
"""

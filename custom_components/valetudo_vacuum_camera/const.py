"""Constants for the valetudo_vacuum_camera integration."""
"""Version 1.1.5"""

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

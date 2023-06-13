"""Constants for the valetudo_vacuum_camera integration."""

"""Required in Config_Flow"""
PLATFORMS = ["camera"]
DOMAIN = "valetudo_vacuum_camera"
DEFAULT_NAME = "valetudo vacuum camera"
CONF_VACUUM_CONNECTION_STRING = "vacuum_map"
CONF_VACUUM_ENTITY_ID = "vacuum_entity"
CONF_MQTT_USER = "MQTT_User"
CONF_MQTT_PASS = "MQTT_Password"
ICON = "mdi:camera"

"""App Constants"""
IDLE_SCAN_INTERVAL = 120
CLEANING_SCAN_INTERVAL = 5

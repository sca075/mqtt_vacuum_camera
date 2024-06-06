"""
Custom HassKey types for Home Assistant.
Version: 2024.06.2
"""

# from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN
from homeassistant.components.mqtt.models import MqttData
from homeassistant.util.hass_dict import HassKey

GET_MQTT_DATA: HassKey[MqttData] = HassKey("mqtt")

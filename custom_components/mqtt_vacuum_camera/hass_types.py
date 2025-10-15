"""
Custom HassKey types for Home Assistant.
Version: 2025.3.0b0
"""

from homeassistant.components.mqtt.models import MqttData
from homeassistant.util.hass_dict import HassKey

GET_MQTT_DATA: HassKey[MqttData] = HassKey("mqtt")

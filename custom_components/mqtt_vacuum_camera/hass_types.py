"""
Custom HassKey types for Home Assistant.
Version: 2024.07.1
"""

from homeassistant.components.mqtt.models import MqttData
from homeassistant.util.hass_dict import HassKey

from .types import TrimCropData

GET_MQTT_DATA: HassKey[MqttData] = HassKey("mqtt")
GET_TRIM_CROP_DATA: HassKey[TrimCropData] = HassKey("trim_crop")

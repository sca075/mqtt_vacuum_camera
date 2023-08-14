""" Class Vacuum to keep and middle connection between
modules:
Not fully implemented yet in consideration"""


import logging
from custom_components.valetudo_vacuum_camera.types import Colors

_LOGGER = logging.getLogger(__name__)


class Vacuum(object):
    """Vacuum Class share the actual Vacuum status and
    other information's grabbed during the execution"""

    def __init__(self):
        self._new_mqtt_message = False
        self._last_image = None
        self.user_colors = Colors
        self.rooms_colors = Colors
        self.vacuum_state = None
        self.vacuum_error = None

    def update_user_colors(self, user_colors):
        self.user_colors = user_colors

    def get_user_colors(self):
        return self.user_colors

    def update_rooms_colors(self, user_colors):
        self.rooms_colors = user_colors

    def get_rooms_colors(self):
        return self.rooms_colors

    def is_data_available(self):
        value = self._new_mqtt_message
        _LOGGER.debug("MQTT data available: %s", value)
        return value

    def set_new_mqtt_data_available(self, value: bool):
        """set_new_mqtt_data_available get on_message state"""
        _LOGGER.debug("MQTT set data available: %s", value)
        self._new_mqtt_message = value

    def set_last_image(self, data):
        self._last_image = data

    def set_vacuum_state(self, data):
        self.vacuum_state = data

    def get_vacuum_state(self):
        return self.vacuum_state

    def last_image_binary(self):
        """last_image_stored
        :return get and return the last
        binary data of the camera precessed image"""
        return self._last_image

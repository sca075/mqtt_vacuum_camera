import logging
#import numpy as np
#from custom_components.valetudo_vacuum_camera.utils.colors import color_home_background

_LOGGER = logging.getLogger(__name__)

class Vacuum(object):
    ''' Vacuum Class share the actual Vacuum status and
        other information's grabbed during the execution '''
    def __init__(self):
        self._new_mqtt_message = False
        self._last_image = None

    def is_data_available(self):
        value = self._new_mqtt_message
        _LOGGER.debug("MQTT data available: %s", value)
        return value

    def set_new_mqtt_data_available(self, value: bool):
        '''set_new_mqtt_data_available get on_message state'''
        _LOGGER.debug("MQTT set data available: %s", value)
        self._new_mqtt_message = value

    def set_last_image(self, data):
        self._last_image = data

    def last_image_binary(self):
        '''last_image_stored
        :return get and return the last
        binary data of the camera precessed image'''
        return self._last_image
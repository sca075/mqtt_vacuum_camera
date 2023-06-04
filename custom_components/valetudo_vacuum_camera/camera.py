from __future__ import annotations

import logging
from io import BytesIO
import voluptuous as vol
from datetime import timedelta
from typing import Optional

from homeassistant.components.camera import (Camera, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_NAME,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.util import Throttle

from custom_components.valetudo_vacuum_camera.valetudo.connector import ValetudoConnector
from custom_components.valetudo_vacuum_camera.valetudo.image_handler import MapImageHandler
from custom_components.valetudo_vacuum_camera.valetudo.vacuum import Vacuum

_LOGGER: logging.Logger = logging.getLogger(__name__)
#_LOGGER = logging.getLogger(__name__)

from .const import (
    CONF_VACUUM_CONNECTION_STRING,
    CONF_VACUUM_ENTITY_ID,
    CONF_MQTT_USER,
    CONF_MQTT_PASS,
    DEFAULT_NAME,
    ICON
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_VACUUM_CONNECTION_STRING): cv.string,
        vol.Required(CONF_VACUUM_ENTITY_ID): cv.string,
        vol.Optional(CONF_MQTT_USER): cv.string,
        vol.Optional(CONF_MQTT_PASS): cv.string,
        vol.Optional(ICON): cv.icon,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    async_add_entities([ValetudoCamera(hass, config)])


class ValetudoCamera(Camera):
    def __init__(self, hass, device_info):
        super().__init__()
        self.hass = hass
        self._name = device_info.get(CONF_NAME)
        self._vacuum_entity = device_info.get(CONF_VACUUM_ENTITY_ID)
        self._attr_unique_id = str(device_info.get(CONF_VACUUM_ENTITY_ID) + "_camera")
        self._mqtt_listen_topic = str(device_info.get(CONF_VACUUM_CONNECTION_STRING))
        self._mqtt_user = str(device_info.get(CONF_MQTT_USER))
        self._mqtt_pass = str(device_info.get(CONF_MQTT_PASS))

        self._mqtt = ValetudoConnector(self._mqtt_user, self._mqtt_pass, self._mqtt_listen_topic, hass)
        self._map_handler = MapImageHandler()
        self._vacuum_shared = Vacuum()

        self._vacuum_state = None
        self._frame_interval = 1
        self._vac_img_data = None
        self._vac_json_data = None
        self._vac_json_id = None
        self._image_scale = None
        self._base = None
        self._current = None
        self._temp_dir = "config/tmp"
        self._image = self.update()
        self._last_image = None
        self.throttled_camera_image = Throttle(timedelta(seconds=5))(self.camera_image)
        self._should_poll = True
        self.async_camera_image(True)

    async def async_added_to_hass(self) -> None:
        self.async_schedule_update_ha_state(True)

    @property
    def frame_interval(self) -> float:
        return 1

    def camera_image(self, width: Optional[int] = None, height: Optional[int] = None) -> Optional[bytes]:
        if self._image is not None:
            self._last_image = self._image
            return self._image
        else:
            return self._last_image

    @property
    def name(self) -> str:
        return self._name

    def turn_on(self):
        self._should_poll = True

    def turn_off(self):
        self._should_poll = False

    @property
    def extra_state_attributes(self):
        return {
            "vacuum_entity": self._vacuum_entity,
            "vacuum_status": self._vacuum_state,
            "vacuum_json_data": self._vac_json_id,
            "robot_position": self._current,
            "charger_position": self._base,
            "json_data": self._vac_json_data,
            "unique_id": self._attr_unique_id,
            "listen_to": self._mqtt_listen_topic
        }

    @property
    def should_poll(self) -> bool:
        return self._should_poll

    def update(self):
        # if we have data from MQTT we process the image
        proces_data = self._mqtt.is_data_available()
        if proces_data:
            _LOGGER.info("camera image update process: %s", proces_data)
            try:
                parsed_json = self._mqtt.update_data()
                self._vac_json_data = "Success"
            except ValueError:
                self._vac_json_data = "Error"
                pass
            else:
                # just in case let's check that the data are available
                if parsed_json is not None:
                    pil_img = self._map_handler.get_image_from_json(parsed_json)
                    self._vac_json_id = self._map_handler.get_json_id()
                    self._base = self._map_handler.get_charger_position()
                    self._current = self._map_handler.get_robot_position()
                    self._vac_img_data = self._map_handler.get_img_size()
                    # Converting to bytes the image got from json.
                    self._image = pil_img.tobytes()
                    self._vacuum_shared.set_last_image(self._image)
                    _LOGGER.info("camera image update complete")
                    return self._image
        else:
            # we don't have data from MQTT, buffered image is returned instead.
            self._image = self._vacuum_shared.last_image_binary()
            _LOGGER.info("camera image from buffer")
            return self._image

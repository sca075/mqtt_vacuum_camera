from __future__ import annotations

import logging
import json
from io import BytesIO
import requests
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

_LOGGER: logging.Logger = logging.getLogger(__name__)
#_LOGGER = logging.getLogger(__name__)

from .const import (
    CONF_VACUUM_CONNECTION_STRING,
    CONF_VACUUM_ENTITY_ID,
    DEFAULT_NAME,
    CONF_MQTT_USER,
    CONF_MQTT_PASS,
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

        self._mqtt = ValetudoConnector(self._mqtt_listen_topic)
        self._map_handler = MapImageHandler()

        self._session = requests.session()
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
        _LOGGER.info("camera image update start")

        test = self._mqtt.update_data(self._mqtt_listen_topic)
        _LOGGER.debug("result: %s", str(test))

        try:
            #test purpose only we retrive the json directly from the vacuum rest api
            #the vacuum is connected via MQTT to a different ha instance
            url = 'http://valetudo-silenttepidstinkbug.local/api/v2/robot/state/map'
            headers = {'accept': 'application/json'}
            self._vac_json_data = "Success"
            response = self._session.get(url, headers=headers, timeout=10)

        except Exception:
            self._vac_json_data = "Error"
            pass
        else:
            resp_data = response.content
            parsed_json = json.loads(resp_data.decode('utf-8'))

            pil_img = self._map_handler.get_image_from_json(parsed_json)
            self._vac_json_id = self._map_handler.get_json_id()
            self._base = self._map_handler.get_charger_position()
            self._current = self._map_handler.get_robot_position()
            self._vac_img_data = self._map_handler.get_img_size()

            # Converting to bites the image got gtom json.
            buffered = BytesIO()
            pil_img.save(buffered, format="PNG")
            bytes_data = buffered.getvalue()
            self._image = bytes_data
            return bytes_data

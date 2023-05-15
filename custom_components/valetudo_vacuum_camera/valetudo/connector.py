import logging
from typing import Optional

from homeassistant.components import camera
from homeassistant.components.camera import Image
from homeassistant.core import HomeAssistant, callback, Config
from homeassistant.exceptions import HomeAssistantError


_LOGGER = logging.getLogger(__name__)


class ValetudoConnector:
    def __init__(self, hass, map_data_entity_id):
        self.two_factor_auth_url = None
        self._hass = hass
        self._map_data_entity_id = map_data_entity_id
        self._raw_map_data = None
        self._vacuum_name = None
        self._name = "Valetudo Map Data Extractor"

    def login(self):
        return True

    def get_mqtt_data(self) -> Optional[bytes]:
        image: Image
        try:

            image = camera.async_get_image(self._hass, self._map_data_entity_id, 30).cr_await

        except HomeAssistantError as err:
            _LOGGER.warning("Error getting image from valetudo camera entity: %s", err)
            return None

        return image.content
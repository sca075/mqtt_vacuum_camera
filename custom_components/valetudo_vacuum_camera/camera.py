from __future__ import annotations

import logging
from io import BytesIO
from datetime import timedelta
from typing import Optional

import voluptuous as vol

from homeassistant.components.camera import Camera, PLATFORM_SCHEMA, SUPPORT_ON_OFF
from homeassistant.const import CONF_NAME
from homeassistant import core, config_entries
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)
from homeassistant.util import Throttle

from custom_components.valetudo_vacuum_camera.valetudo.connector import (
    ValetudoConnector,
)
from custom_components.valetudo_vacuum_camera.valetudo.image_handler import (
    MapImageHandler,
)
from custom_components.valetudo_vacuum_camera.valetudo.vacuum import Vacuum

_LOGGER: logging.Logger = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)

from .const import (
    CONF_VACUUM_CONNECTION_STRING,
    CONF_VACUUM_ENTITY_ID,
    CONF_MQTT_USER,
    CONF_MQTT_PASS,
    DEFAULT_NAME,
    DOMAIN,
    PLATFORMS,
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_VACUUM_CONNECTION_STRING): cv.string,
        vol.Required(CONF_VACUUM_ENTITY_ID): cv.string,
        vol.Required(CONF_MQTT_USER): cv.string,
        vol.Required(CONF_MQTT_PASS): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
) -> None:
    """Setup camera from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    # Update our config to and eventually add or remove option.
    if config_entry.options:
        config.update(config_entry.options)
    camera = [ValetudoCamera(Camera, config)]
    async_add_entities(camera, update_before_add=True)


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities,
    discovery_info: DiscoveryInfoType | None = None,
):
    async_add_entities([ValetudoCamera(hass, config)])
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)


class ValetudoCamera(Camera, Entity):
    def __init__(self, hass, device_info):
        super().__init__()
        self.hass = hass
        self._name = device_info.get(CONF_NAME)
        self._attr_unique_id = "_"  # uses the config name for unique id
        self._vacuum_entity = device_info.get(CONF_VACUUM_ENTITY_ID)
        self._mqtt_listen_topic = device_info.get(CONF_VACUUM_CONNECTION_STRING)
        if self._mqtt_listen_topic:
            self._mqtt_listen_topic = str(self._mqtt_listen_topic)
        self._mqtt_user = device_info.get(CONF_MQTT_USER)
        self._mqtt_pass = device_info.get(CONF_MQTT_PASS)
        self._mqtt = ValetudoConnector(
            self._mqtt_user, self._mqtt_pass, self._mqtt_listen_topic, hass
        )
        self._map_handler = MapImageHandler()
        self._vacuum_shared = Vacuum()
        self._vacuum_state = None
        self._frame_interval = 1
        self._vac_img_data = None
        self._vac_json_data = None
        self._vac_json_id = None
        self._calibration_points = None
        self._base = None
        self._current = None
        self._temp_dir = "config/tmp"
        self._image_rotate = 180
        self._image = self.update()
        self._last_image = None
        self.throttled_camera_image = Throttle(timedelta(seconds=5))(self.camera_image)
        self._should_poll = True

    async def async_added_to_hass(self) -> None:
        self.async_schedule_update_ha_state(True)

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal from Home Assistant."""
        await super().async_will_remove_from_hass()

        # Stop the camera and perform any necessary cleanup tasks here
        self.turn_off()

    @property
    def frame_interval(self) -> float:
        return 1

    def camera_image(
        self, width: Optional[int] = None, height: Optional[int] = None
    ) -> Optional[bytes]:
        return self._image

    @property
    def name(self) -> str:
        return self._name

    def turn_on(self):
        self._mqtt.client_start()
        self._should_poll = True

    def turn_off(self):
        self._mqtt.client_stop()
        self._should_poll = False

    @property
    def supported_features(self) -> int:
        return SUPPORT_ON_OFF

    @property
    def extra_state_attributes(self):
        return {
            "vacuum_entity": self._vacuum_entity,
            "vacuum_status": self._vacuum_state,
            "vacuum_json_id": self._vac_json_id,
            "robot_position": self._current,
            "calibration_points": self._calibration_points,
            "json_data": self._vac_json_data,
            "listen_to": self._mqtt_listen_topic,
        }

    @property
    def should_poll(self) -> bool:
        return self._should_poll

    def update(self):
        # If we have data from MQTT, we process the image
        process_data = self._mqtt.is_data_available()
        if process_data:
            _LOGGER.info("Camera image update process: %s", process_data)
            try:
                parsed_json = self._mqtt.update_data()
                self._vac_json_data = "Success"
            except ValueError:
                self._vac_json_data = "Error"
                pass
            else:
                # Just in case, let's check that the data is available
                if parsed_json is not None:
                    pil_img = self._map_handler.get_image_from_json(parsed_json)
                    pil_img = pil_img.rotate(self._image_rotate)
                    self._vacuum_state = self._mqtt.get_vacuum_status()
                    self._vac_json_id = self._map_handler.get_json_id()
                    self._base = self._map_handler.get_charger_position()
                    self._current = self._map_handler.get_robot_position()
                    self._vac_img_data = self._map_handler.get_img_size()
                    _LOGGER.debug(self._image_rotate)
                    self._calibration_points = self._map_handler.get_calibration_data(
                        self._image_rotate
                    )
                    # Converting the image obtained from JSON to bytes

                    buffered = BytesIO()
                    pil_img.save(buffered, format="PNG")
                    bytes_data = buffered.getvalue()
                    self._image = bytes_data
                    _LOGGER.info("Camera image update complete")
                    return self._image

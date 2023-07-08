"""Config Flow Version 1.1.5"""
import voluptuous as vol
import logging
from typing import Any, Dict, Optional

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_VACUUM_ENTITY_ID,
    CONF_VACUUM_CONNECTION_STRING,
    CONF_MQTT_USER,
    CONF_MQTT_PASS,
    DEFAULT_NAME,
    ATT_ROTATE,
    ATT_CROP,
)

_LOGGER = logging.getLogger(__name__)

AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VACUUM_ENTITY_ID): cv.string,
        vol.Required(CONF_MQTT_USER): cv.string,
        vol.Required(CONF_MQTT_PASS): cv.string,
        vol.Required(CONF_VACUUM_CONNECTION_STRING): cv.string,
        vol.Required(ATT_ROTATE, default="0"): cv.string,
        vol.Required(ATT_CROP, default="0"): cv.string,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {vol.Optional(CONF_NAME, default="valetudo_vacuum_camera"): cv.entity_id}
)


class ValetudoCameraFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    def __init__(self):
        self.data = None

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        if user_input is not None:
            self.data = user_input
            self.data.update(
                {
                    "vacuum_entity": user_input.get(CONF_VACUUM_ENTITY_ID),
                    "broker_user": user_input.get(CONF_MQTT_USER),
                    "broker_password": user_input.get(CONF_MQTT_PASS),
                    "vacuum_map": user_input.get(CONF_VACUUM_CONNECTION_STRING),
                    "rotate_image": user_input.get(ATT_ROTATE),
                    "crop_image": user_input.get(ATT_CROP),
                }
            )
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data=user_input,
            )

        return self.async_show_form(step_id="user", data_schema=AUTH_SCHEMA)

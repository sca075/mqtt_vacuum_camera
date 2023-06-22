import voluptuous as vol
import logging
from typing import Any, Dict, Optional

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

from .const import (
    DOMAIN,
    CONF_VACUUM_ENTITY_ID,
    CONF_VACUUM_CONNECTION_STRING,
    CONF_MQTT_USER,
    CONF_MQTT_PASS,
    DEFAULT_NAME,
)

AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VACUUM_ENTITY_ID): cv.string,
        vol.Required(CONF_MQTT_USER): cv.string,
        vol.Required(CONF_MQTT_PASS): cv.string,
        vol.Required(CONF_VACUUM_CONNECTION_STRING): cv.string
    }
)

OPTIONS_SCHEMA = vol.Schema({vol.Optional(CONF_NAME, default="valetudo_vacuum_camera"): cv.string})

class ValetudoCameraFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):

        if user_input is not None:

            self.data = user_input

            self.data.update(
                {
                    "vacuum_entity": user_input.get(CONF_VACUUM_ENTITY_ID),
                    "broker_user": user_input.get(CONF_MQTT_USER),
                    "broker_password": user_input.get(CONF_MQTT_PASS),
                    "vacuum_map": user_input.get(CONF_VACUUM_CONNECTION_STRING)
                }
            )
            return self.async_create_entry(
                title=DEFAULT_NAME, data=user_input,
            )

        return self.async_show_form(
            step_id="user", data_schema=AUTH_SCHEMA
        )

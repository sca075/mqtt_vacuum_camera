import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.exceptions import ConfigEntryAuthFailed, Unauthorized, UnknownUser

from .const import CONF_VACUUM_CONNECTION_STRING, CONF_VACUUM_ENTITY_ID, DEFAULT_NAME, DOMAIN, ICON

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VACUUM_ENTITY_ID): cv.string,
        vol.Required(CONF_VACUUM_CONNECTION_STRING): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def validate_input(hass, data):
    entity_id = data.get(CONF_VACUUM_ENTITY_ID)
    mqtt_entity_id = data.get(CONF_VACUUM_CONNECTION_STRING)

    # Check if vacuum entity exists
    if not hass.states.get(entity_id):
        raise vol.Invalid("Invalid vacuum entity ID")

    # Check if MQTT image entity exists
    if not hass.states.get(mqtt_entity_id):
        raise vol.Invalid("MQTT image entity does not exist")

    return data


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Valetudo Camera."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            # Check if the vacuum entity exists
            self.CONF_VACUUM_ENTITY_ID = user_input[vacuum_entity]
            self.CONF_VACUUM_CONNECTION_STRING = user_input[vacuum_map]

        # Removed as temporally error handling
        #"error": {
        #    "cannot_connect": "Could not connect to vacuum. Please check the connection and try again.",
        #    "invalid_auth": "Invalid authentication credentials. Please check and try again.",
        #    "unknown": "Unknown error occurred while connecting to vacuum. Please check the connection and try again."
        #},

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

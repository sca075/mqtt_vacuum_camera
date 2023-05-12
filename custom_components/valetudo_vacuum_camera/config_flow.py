import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv

from .const import CONF_VACUUM_CONNECTION_STRING, CONF_VACUUM_ENTITY_ID, DEFAULT_NAME, DOMAIN


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
    mqtt_entity_id = "mqtt.camera_{}_map".format(entity_id.split('.')[1])

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
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            # Check if the vacuum entity exists
            vacuum_entity = user_input.get(CONF_VACUUM_ENTITY_ID)
            entity_registry = await self.hass.helpers.entity_registry.async_get_registry()
            if vacuum_entity not in entity_registry.entities:
                errors["base"] = "invalid_entity_id"
            else:
                # Check if the MQTT image entity exists
                mqtt_entity_id = f"camera.{user_input[CONF_NAME].lower()}_map"
                if mqtt_entity_id not in entity_registry.entities:
                    errors["base"] = "missing_mqtt_entity_id"
                else:
                    # Try to validate the input
                    try:
                        info = await validate_input(self.hass, user_input)
                        return self.async_create_entry(
                            title=user_input[CONF_NAME],
                            data={
                                CONF_VACUUM_ENTITY_ID: user_input[CONF_VACUUM_ENTITY_ID],
                                CONF_VACUUM_CONNECTION_STRING: user_input[CONF_VACUUM_CONNECTION_STRING],
                            },
                        )
                    except CannotConnectError:
                        errors["base"] = "cannot_connect"
                    except InvalidAuthError:
                        errors["base"] = "invalid_auth"
                    except UnknownError:
                        errors["base"] = "unknown_error"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_VACUUM_ENTITY_ID): cv.string,
                    vol.Required(CONF_VACUUM_CONNECTION_STRING): cv.string,
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                }
            ),
            errors=errors,
        )
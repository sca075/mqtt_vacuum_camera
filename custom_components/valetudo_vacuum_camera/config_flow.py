import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VACUUM_ENTITY_ID): str,
        vol.Required(CONF_VACUUM_CONNECTION_STRING): str,
        vol.Optional(CONF_NAME, default="Valetudo Vacuum"): str,
    }
)


async def validate_input(hass, data):
    session = async_create_clientsession(hass)
    try:
        valetudo = await hass.async_add_executor_job(
            ValetudoAPI, data[CONF_VACUUM_ENTITY_ID], data[CONF_VACUUM_CONNECTION_STRING], session
        )
        status = await valetudo.get_status()
    except CannotConnect:
        raise CannotConnectError
    except Unauthorized:
        raise InvalidAuthError
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.error("Unexpected exception %s", ex)
        raise UnknownError

    return {"status": status}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Valetudo Camera."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self._show_form()

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnectError:
            return self.async_abort(reason="cannot_connect")
        except InvalidAuthError:
            return self.async_abort(reason="invalid_auth")
        except UnknownError:
            return self.async_abort(reason="unknown")

        name = user_input[CONF_NAME]
        host = user_input[CONF_HOST]
        token = user_input[CONF_TOKEN]

        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=name, data={CONF_HOST: host, CONF_TOKEN: token}
        )

    def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors or {}
        )

import voluptuous as vol
import logging

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

from .const import (
    DOMAIN,
    CONF_VACUUM_ENTITY_ID,
    CONF_VACUUM_CONNECTION_STRING
)


class ValetudoCameraFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    _LOGGER.info("Loading Config Flow")

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        self.vacuum_entity = ""
        self.vacuum_map = ""

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self.vacuum_entity = user_input.get(CONF_VACUUM_ENTITY_ID)
            self.vacuum_map = user_input.get(CONF_VACUUM_CONNECTION_STRING)

            return self.async_create_entry(
                title=self.vacuum_entity, data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_VACUUM_ENTITY_ID, default=self.vacuum_entity or "vacuum"): str,
                    vol.Required(CONF_VACUUM_CONNECTION_STRING, default=self.vacuum_map or "map"): str,
                }
            ),
        )

        await self.async_set_unique_id(device_unique_id)
        self._abort_if_unique_id_configured()

    #async def async_get_options_flow(self, config):
    #    """Define the configuration flow to manage options."""
    #    return OptionsFlowHandler(self)

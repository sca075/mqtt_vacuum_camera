import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    CONF_VACUUM_ENTITY,
    CONF_VACUUM_MAP
)


    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self.vacuum_entity = user_input.get(CONF_VACUUM_ENTITY)
            self.vacuum_map = user_input.get(CONF_VACUUM_MAP)

            return self.async_create_entry(
                title=self.vacuum_entity, data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_VACUUM_ENTITY, default=self.vacuum_entity or ""): str,
                    vol.Optional(CONF_VACUUM_MAP, default=self.vacuum_map or ""): str,
                }
            ),
        )

class ValetudoCameraFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        self.vacuum_entity = ""
        self.vacuum_map = ""

class ValetudoCameraOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for a config entry."""

    def __init__(self, config_entry):
        """Initialize the options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            unique_id = user_input.get(CONF_UNIQUE_ID)

            # Update the unique_id of the config entry.
            self.hass.config_entries.async_update_entry(
                self.config_entry, unique_id=unique_id
            )

            # Return to the previous options screen.
            return self.async_create_entry(title="", data={})

        # Display the options form.
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_UNIQUE_ID, default=self.config_entry.unique_id
                    ): str
                }
            ),
        )

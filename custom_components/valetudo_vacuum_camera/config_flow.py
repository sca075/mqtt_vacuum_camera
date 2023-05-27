import voluptuous as vol
import logging

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow

_LOGGER = logging.getLogger(__name__)

from .const import (
    DOMAIN,
    CONF_VACUUM_ENTITY_ID,
    CONF_VACUUM_CONNECTION_STRING,
    CONF_MQTT_USER,
    CONF_MQTT_PASS,
    DEFAULT_NAME
)

class ValetudoCameraFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        self.vacuum_entity = ""
        self.vacuum_map = ""
        self.mqtt_user = ""
        self.mqtt_pass = ""

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self.vacuum_entity = user_input.get(CONF_VACUUM_ENTITY_ID)
            self.vacuum_map = user_input.get(CONF_VACUUM_CONNECTION_STRING)
            self.mqtt_user = user_input.get(CONF_MQTT_USER)
            self.mqtt_pass = user_input.get(CONF_MQTT_PASS)

            device_unique_id = f"{self.vacuum_entity}_camera"

            return self.async_create_entry(
                title=DEFAULT_NAME, data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_VACUUM_ENTITY_ID, default=self.vacuum_entity or "vacuum"): str,
                    vol.Optional(CONF_VACUUM_CONNECTION_STRING, default=self.vacuum_map or "map"): str,
                    vol.Optional(CONF_MQTT_USER, default=self.mqtt_user or "mqtt_user"): str,
                    vol.Optional(CONF_MQTT_PASS, default=self.mqtt_pass or "mqtt_password"): str,
                }
            ),
        )

        await self.async_set_unique_id(device_unique_id)
        self._abort_if_unique_id_configured()

    async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
        """Set up the platform from a ConfigEntry."""
        # Perform setup tasks specific to your platform
        # Use the provided `entry` object to access configuration data

        # Example: Forward the setup to the camera platform
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "camera")
        )

        # Return True if the setup was successful
        return True

config_entry_flow.register_discovery_flow(
    DOMAIN, DEFAULT_NAME, lambda _: None, config_entries.CONN_CLASS_LOCAL_PUSH
)

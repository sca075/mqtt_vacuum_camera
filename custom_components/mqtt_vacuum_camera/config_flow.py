"""
config_flow.py
IMPORTANT: Maintain code when adding new options to the camera
it will be mandatory to update const.py and common.py update_options.
Format of the new constants must be CONST_NAME = "const_name" update also
sting.json and en.json please.
Version: 2025.3.0b1
"""

import os
from typing import Any, Dict, Optional

from homeassistant import config_entries
from homeassistant.components.vacuum import DOMAIN as ZONE_VACUUM
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig
from homeassistant.helpers.storage import STORAGE_DIR
import voluptuous as vol

from .common import (
    get_vacuum_device_info,
    get_vacuum_mqtt_topic,
    get_vacuum_unique_id_from_mqtt_topic,
)
from .const import (
    CAMERA_STORAGE,
    CONF_VACUUM_CONFIG_ENTRY_ID,
    CONF_VACUUM_ENTITY_ID,
    DEFAULT_VALUES,
    DOMAIN,
    LOGGER,
)
from .options_flow import MQTTCameraOptionsFlowHandler

VACUUM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VACUUM_ENTITY_ID): EntitySelector(
            EntitySelectorConfig(domain=ZONE_VACUUM),
        )
    }
)


class MQTTCameraFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Camera Configration Flow Handler"""

    VERSION = 3.3

    def __init__(self):
        self.data = {}
        self.camera_options = {}
        self.name = ""

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        if user_input is not None:
            vacuum_entity_id = user_input["vacuum_entity"]
            entity_registry = er.async_get(self.hass)
            vacuum_entity = entity_registry.async_get(vacuum_entity_id)
            vacuum_topic = get_vacuum_mqtt_topic(vacuum_entity_id, self.hass)
            if not vacuum_topic:
                raise ConfigEntryError(
                    f"Vacuum {vacuum_entity_id} not supported! No MQTT topic found."
                )

            unique_id = get_vacuum_unique_id_from_mqtt_topic(vacuum_topic)

            for existing_entity in self._async_current_entries():
                if (
                    existing_entity.data.get(CONF_VACUUM_ENTITY_ID) == vacuum_entity.id
                    or existing_entity.data.get(CONF_UNIQUE_ID) == unique_id
                ):
                    return self.async_abort(reason="already_configured")

            self.data.update(
                {
                    CONF_VACUUM_CONFIG_ENTRY_ID: vacuum_entity.id,
                    CONF_UNIQUE_ID: unique_id,
                    "platform": "mqtt_vacuum_camera",
                }
            )

            # set the unique_id in the entry configuration
            await self.async_set_unique_id(unique_id=unique_id)
            # set default options
            self.camera_options.update(DEFAULT_VALUES)
            # create the path for storing the snapshots.
            storage_path = f"{self.hass.config.path(STORAGE_DIR)}/{CAMERA_STORAGE}"
            if not os.path.exists(storage_path):
                LOGGER.debug("Creating the %s path.", storage_path)
                try:
                    os.mkdir(storage_path)
                except FileExistsError as e:
                    LOGGER.error(
                        "Error %s can not find path %s", e, storage_path, exc_info=True
                    )
                except OSError as e:
                    LOGGER.error(
                        "Error %s creating the path %s", e, storage_path, exc_info=True
                    )
            else:
                LOGGER.debug("Storage %s path found.", storage_path)
            # Finally set up the entry.
            _, vacuum_device = get_vacuum_device_info(
                self.data[CONF_VACUUM_CONFIG_ENTRY_ID], self.hass
            )

            # Return the data and default options to config_entry
            return self.async_create_entry(
                title=vacuum_device.name + " Camera",
                data=self.data,
                options=self.camera_options,
            )

        return self.async_show_form(step_id="user", data_schema=VACUUM_SCHEMA)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return MQTTCameraOptionsFlowHandler(config_entry)

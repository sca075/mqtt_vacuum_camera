from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType

from .custom_componets import (

)

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the MQTT connector component."""
    topic = config[DOMAIN][CONF_TOPIC]
    entity_id = 'camera.valetudo_vacuum_camera'

    # Callback function to update the camera entity with received MQTT message
    @callback
    def message_received(topic: str, payload: str, qos: int) -> None:
        """A new MQTT message has been received."""
        hass.states.async_set(entity_id, {'image': payload})

    # Subscribe to the MQTT topic and register the callback function
    await hass.components.mqtt.async_subscribe(topic, message_received)

    # Set the initial state of the camera entity
    hass.states.async_set(entity_id, {'image': None})

    # Return boolean to indicate that initialization was successful
    return True

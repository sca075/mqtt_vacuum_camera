import json
import logging

import homeassistant.helpers.entity as ha_entity
import homeassistant.components.mqtt as mqtt

_LOGGER = logging.getLogger(__name__)


class MQTTConnector(ha_entity.Entity):
    def __init__(self, hass, config):
        self._hass = hass
        self._config = config
        self._mqtt_payload = None
        self._mqtt_topic = None

    async def async_added_to_hass(self):
        self._mqtt_topic = self._config.get('topic')
        self._mqtt_client = mqtt.async_get_client(self._hass)

        async def message_received(topic, payload, qos):
            try:
                payload = json.loads(payload)
                self._mqtt_payload = payload
            except ValueError:
                _LOGGER.error("Unable to parse JSON payload: %s", payload)

        await self._hass.async_create_task(
            self._mqtt_client.async_subscribe(self._mqtt_topic, message_received)
        )

    async def async_will_remove_from_hass(self) -> None:
        await self._mqtt_client.async_unsubscribe(self._mqtt_topic)

    async def async_publish(self, topic, payload, qos=0, retain=False):
        await self._mqtt_client.async_publish(topic, payload, qos, retain)

    @property
    def state(self):
        return self._mqtt_payload

    @property
    def name(self):
        return 'mqtt_connector'

    @property
    def unique_id(self):
        return 'mqtt_connector'

    @property
    def icon(self):
        return 'mdi:cloud'

    @property
    def device_state_attributes(self):
        return self._mqtt_payload

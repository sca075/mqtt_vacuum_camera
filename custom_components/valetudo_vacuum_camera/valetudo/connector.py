"""
Version 1.4.5
- Removed the PNG decode, the json is extracted from map-data instead of map-data hass.
- Valetudo Re vacuum payload is going to be save on the WWW folder file "mqtt_valetudo_re.raw".
- Tested no influence on the camera performance.
"""
import logging
import os
import json
import zlib
from homeassistant.core import callback
from homeassistant.components import mqtt

from custom_components.valetudo_vacuum_camera.valetudo.valetudore.rrparser import RRMapParser

_LOGGER = logging.getLogger(__name__)
_QOS = 0


class ValetudoConnector:
    def __init__(self, mqtt_topic, hass):
        self._hass = hass
        self._mqtt_topic = mqtt_topic
        self._unsubscribe_handlers = []
        self._rcv_topic = None
        self._payload = None
        self._img_payload = None
        self._mqtt_vac_stat = None
        self._mqtt_vac_err = None
        self._data_in = False
        self._rnd_payload = None  # Payload from Valetudo Re
        self._rand_data = RRMapParser

    async def update_data(self, process: bool = True):
        if self._img_payload:
            if process:
                _LOGGER.debug("Processing " + self._mqtt_topic + " data from MQTT")
                json_data = zlib.decompress(self._img_payload).decode("utf-8")
                result = json.loads(json_data)
                _LOGGER.debug(self._mqtt_topic + ": Extracting JSON Complete")
                self._data_in = False
                return result
            else:
                _LOGGER.debug("No data from " + self._mqtt_topic + " or vacuum docked")
                self._data_in = False
                return None

    async def get_vacuum_status(self):
        return self._mqtt_vac_stat

    async def get_vacuum_error(self):
        return self._mqtt_vac_err

    async def is_data_available(self):
        return self._data_in

    def save_payload(self, file_name):
        # save payload when available.
        if (self._img_payload and (self._data_in is True)) or \
                (self._rnd_payload is not None):
            file_data = "No data"
            if self._img_payload:
                file_data = self._img_payload
            elif self._rnd_payload:
                file_data = self._rnd_payload
            with open(
                    str(os.getcwd())
                    + "/www/"
                    + file_name
                    + ".raw",
                    "wb",
            ) as file:
                file.write(file_data)
            _LOGGER.info("Saved image data from MQTT in mqtt_" + file_name + ".raw!")

    @callback
    async def async_message_received(self, msg):
        self._rcv_topic = msg.topic
        if self._rcv_topic == (self._mqtt_topic + "/map_data"):  # Attempt get ValetudoRe data.
            self._rnd_payload = self._rcv_topic
            self.save_payload("valetudo_re")
            tmp_json = await self._rand_data.PARSE(self._rnd_payload)
            # tmp_json.update(self._rand_data.PARSEDATA(self._rnd_payload))
            _LOGGER.debug("got RAND payload: %s", tmp_json)
        if self._rcv_topic == self._mqtt_topic + "/MapData/map-data":
            _LOGGER.debug("Received " + self._mqtt_topic + " image data from MQTT")
            self._img_payload = msg.payload
            self._data_in = True
        elif self._rcv_topic == (self._mqtt_topic + "/StatusStateAttribute/status"):
            self._payload = msg.payload
            if self._payload:
                self._mqtt_vac_stat = bytes.decode(self._payload, "utf-8")
                _LOGGER.debug(
                    self._mqtt_topic
                    + ": Received vacuum "
                    + self._mqtt_vac_stat
                    + " status from MQTT:"
                    + self._rcv_topic
                )
        elif self._rcv_topic == (self._mqtt_topic + "/state"):  # for ValetudoRe
            self._payload = msg.payload
            if self._payload:
                tmp_data = json.loads(self._payload)
                self._mqtt_vac_stat = tmp_data.get("state", None)
                _LOGGER.debug(
                    self._mqtt_topic
                    + ": Received vacuum "
                    + self._mqtt_vac_stat
                    + " status from MQTT:"
                    + self._rcv_topic
                )
        elif self._rcv_topic == (
                self._mqtt_topic + "/StatusStateAttribute/error_description"
        ):
            self._payload = msg.payload
            self._mqtt_vac_err = bytes.decode(msg.payload, "utf-8")
            _LOGGER.debug(
                self._mqtt_topic
                + ": Received vacuum "
                + self._mqtt_vac_err
                + " from MQTT"
            )

    async def async_subscribe_to_topics(self):
        if self._mqtt_topic:
            for x in [
                self._mqtt_topic + "/MapData/map-data",
                self._mqtt_topic + "/StatusStateAttribute/status",
                self._mqtt_topic + "/StatusStateAttribute/error_description",
                self._mqtt_topic + "/map_data",  # added for ValetudoRe
                self._mqtt_topic + "/state",  # added for ValetudoRe
            ]:
                self._unsubscribe_handlers.append(
                    await mqtt.async_subscribe(
                        self._hass, x, self.async_message_received, _QOS, encoding=None
                    )
                )

    async def async_unsubscribe_from_topics(self):
        map(lambda x: x(), self._unsubscribe_handlers)

    @staticmethod
    def get_test_payload(payload_data):
        ValetudoConnector._img_payload = payload_data
        _LOGGER.debug("Processing Test Data..")
        ValetudoConnector._data_in = True

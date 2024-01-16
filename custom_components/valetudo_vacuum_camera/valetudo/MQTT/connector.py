"""
Version 1.5.2
- Removed the PNG decode, the json is extracted from map-data instead of map-data hass.
- Tested no influence on the camera performance.
- Added gzip library used in Valetudo RE data compression.
"""
import gzip
import json
import logging
import os
import zlib

from homeassistant.components import mqtt
from homeassistant.core import callback

from custom_components.valetudo_vacuum_camera.valetudo.valetudore.rrparser import (
    RRMapParser,
)

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
        # Payload and data from Valetudo Re
        self._do_it_once = True
        self._is_rrm = None
        self._rrm_json = None
        self._rrm_payload = None
        self._rrm_destinations = None
        self._mqtt_vac_re_stat = None
        self._rrm_data = RRMapParser()

    async def update_data(self, process: bool = True):
        if self._img_payload:
            if process:
                _LOGGER.debug("Processing " + self._mqtt_topic + " data from MQTT")
                json_data = zlib.decompress(self._img_payload).decode("utf-8")
                result = json.loads(json_data)
                _LOGGER.info(self._mqtt_topic + ": Extracting JSON Complete")
                self._data_in = False
                self._is_rrm = False
                self._img_payload = None
                return result, self._is_rrm
            else:
                _LOGGER.info("No data from " + self._mqtt_topic + " or vacuum docked")
                self._data_in = False
                self._is_rrm = False
                return None, self._is_rrm
        elif self._rrm_payload:
            if process:
                _LOGGER.debug("Processing " + self._mqtt_topic + " raw data from MQTT")
                # parse the RRM topic
                payload_decompressed = gzip.decompress(
                    self._rrm_payload
                )  # fix issue with the RE payload.
                self._rrm_json = self._rrm_data.parse_data(
                    payload=payload_decompressed, pixels=True
                )
                self._is_rrm = True
                self._data_in = False
                self._rrm_payload = None
                _LOGGER.info("got Valetudo RE image payload: %s", self._is_rrm)
                return self._rrm_json, self._is_rrm
            else:
                _LOGGER.info("No data from " + self._mqtt_topic + " or vacuum docked")
                self._data_in = False
                self._is_rrm = False
                return None, self._is_rrm

    async def get_vacuum_status(self):
        if self._mqtt_vac_stat:
            return self._mqtt_vac_stat
        if self._mqtt_vac_re_stat:
            return self._mqtt_vac_re_stat

    async def get_vacuum_error(self):
        return self._mqtt_vac_err

    async def is_data_available(self, process):
        if not process:
            return self._data_in
        else:
            return False

    async def get_destinations(self):
        return self._rrm_destinations

    async def save_payload(self, file_name):
        # save payload when available.
        if (self._img_payload and (self._data_in is True)) or (
            self._rrm_payload is not None
        ):
            file_data = b"No data"
            if self._img_payload:
                file_data = self._img_payload
            elif self._rrm_payload:
                file_data = self._rrm_payload
            with open(
                str(os.getcwd()) + "/www/" + file_name + ".raw",
                "wb",
            ) as file:
                file.write(file_data)
            _LOGGER.info("Saved image data from MQTT in mqtt_" + file_name + ".raw!")

    @callback
    async def async_message_received(self, msg):
        self._rcv_topic = msg.topic
        if self._rcv_topic == (self._mqtt_topic + "/map_data"):
            if not self._data_in:
                _LOGGER.info(
                    "Received Valetudo RE " + self._mqtt_topic + " image data from MQTT"
                )
                self._rrm_payload = (
                    msg.payload
                )  # RRM Image data update the received payload
                self._data_in = True
                self._is_rrm = True
                if self._do_it_once:
                    _LOGGER.debug(
                        "Do it once.. request destinations to: %s", self._mqtt_topic
                    )
                    await self.rrm_publish_destinations()
                    self._do_it_once = False
        elif self._rcv_topic == self._mqtt_topic + "/MapData/map-data":
            if not self._data_in:
                _LOGGER.info("Received " + self._mqtt_topic + " image data from MQTT")
                self._img_payload = msg.payload
                self._data_in = True
                self._is_rrm = False
        elif self._rcv_topic == (self._mqtt_topic + "/StatusStateAttribute/status"):
            self._payload = msg.payload
            if self._payload:
                self._mqtt_vac_stat = bytes.decode(self._payload, "utf-8")
                _LOGGER.info(
                    self._mqtt_topic
                    + ": Received vacuum "
                    + self._mqtt_vac_stat
                    + " status."
                )
        elif self._rcv_topic == (self._mqtt_topic + "/state"):  # for ValetudoRe
            self._payload = msg.payload
            if self._payload:
                tmp_data = json.loads(self._payload)
                self._mqtt_vac_re_stat = tmp_data.get("state", None)
                _LOGGER.info(
                    self._mqtt_topic
                    + ": Received vacuum "
                    + self._mqtt_vac_re_stat
                    + " status."
                )
        elif self._rcv_topic == (
            self._mqtt_topic + "/StatusStateAttribute/error_description"
        ):
            self._payload = msg.payload
            self._mqtt_vac_err = bytes.decode(msg.payload, "utf-8")
            _LOGGER.info(
                self._mqtt_topic + ": Received vacuum Error: " + self._mqtt_vac_err
            )
        elif self._rcv_topic == (self._mqtt_topic + "/destinations"):
            self._payload = msg.payload
            tmp_data = bytes.decode(msg.payload, "utf-8")
            self._rrm_destinations = tmp_data
            _LOGGER.info(
                self._mqtt_topic
                + ": Received vacuum destinations. "
                + self._rrm_destinations
            )

    async def async_subscribe_to_topics(self):
        if self._mqtt_topic:
            for x in [
                self._mqtt_topic + "/MapData/map-data",
                self._mqtt_topic + "/StatusStateAttribute/status",
                self._mqtt_topic + "/StatusStateAttribute/error_description",
                self._mqtt_topic + "/map_data",  # added for ValetudoRe
                self._mqtt_topic + "/state",  # added for ValetudoRe
                self._mqtt_topic + "/destinations",  # added for ValetudoRe
            ]:
                self._unsubscribe_handlers.append(
                    await mqtt.async_subscribe(
                        self._hass, x, self.async_message_received, _QOS, encoding=None
                    )
                )

    async def rrm_publish_destinations(self):
        cust_payload = {"command": "get_destinations"}
        cust_payload = json.dumps(cust_payload)
        await mqtt.async_publish(
            self._hass,
            self._mqtt_topic + "/custom_command",
            cust_payload,
            _QOS,
            encoding="utf-8",
        )

    async def async_unsubscribe_from_topics(self):
        _LOGGER.debug("Unsubscribing topics!!!")
        map(lambda x: x(), self._unsubscribe_handlers)

    @staticmethod
    def get_test_payload(payload_data):
        ValetudoConnector._img_payload = payload_data
        _LOGGER.debug("Processing Test Data..")
        ValetudoConnector._data_in = True

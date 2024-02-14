"""
Version 1.5.8
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
from homeassistant.helpers.storage import STORAGE_DIR

from custom_components.valetudo_vacuum_camera.valetudo.valetudore.rrparser import (
    RRMapParser,
)

_LOGGER = logging.getLogger(__name__)
_QOS = 0


class ValetudoConnector:
    """Valetudo MQTT Connector."""

    def __init__(self, mqtt_topic, hass, camera_shared):
        self._hass = hass
        self._mqtt_topic = mqtt_topic
        self._unsubscribe_handlers = []
        self._ignore_data = False
        self._rcv_topic = None
        self._payload = None
        self._img_payload = None
        self._mqtt_vac_stat = ""
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
        self._shared = camera_shared

    async def update_data(self, process: bool = True):
        """
        Update the data from MQTT.
        If it is a Valetudo RE, it will request the destinations.
        When the data is available, it will process it if the camera isn't busy.
        It simply unzips the data and returns the JSON.
        """
        if self._img_payload:
            if process:
                _LOGGER.debug(f"Processing {self._mqtt_topic} data from MQTT")
                json_data = zlib.decompress(self._img_payload).decode("utf-8")
                result = json.loads(json_data)
                _LOGGER.info(self._mqtt_topic + ": Extracting JSON Complete")
                self._data_in = False
                self._is_rrm = False
                self._img_payload = None
                return result, self._is_rrm
            else:
                _LOGGER.info(f"No data from {self._mqtt_topic},"
                             f"vacuum in { self._mqtt_vac_stat} status.")
                self._ignore_data = True
                self._data_in = False
                self._is_rrm = False
                return None, self._is_rrm
        elif self._rrm_payload:
            if process:
                _LOGGER.debug(f"Processing {self._mqtt_topic} raw data from MQTT")
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
                _LOGGER.info(f"got Valetudo RE image payload: {self._is_rrm}")
                return self._rrm_json, self._is_rrm
            else:
                _LOGGER.info(f"No data from {self._mqtt_topic} or vacuum docked")
                self._data_in = False
                self._is_rrm = False
                return None, self._is_rrm

    async def get_vacuum_status(self) -> str:
        """Return the vacuum status."""
        if self._mqtt_vac_stat:
            return self._mqtt_vac_stat
        if self._mqtt_vac_re_stat:
            return self._mqtt_vac_re_stat

    async def get_vacuum_error(self) -> str:
        """Return the vacuum error."""
        return self._mqtt_vac_err

    async def is_data_available(self) -> bool:
        """Check and Return the data availability."""
        return self._data_in

    async def get_destinations(self):
        """Return the destinations used only for Rand256."""
        return self._rrm_destinations

    async def save_payload(self, file_name: str) -> None:
        """
        Save payload when available.
        """
        if (self._img_payload and (self._data_in is True)) or (
            self._rrm_payload is not None
        ):
            file_data = b"No data"
            if self._img_payload:
                file_data = self._img_payload
            elif self._rrm_payload:
                file_data = self._rrm_payload
            with open(
                f"{str(os.getcwd())}/{STORAGE_DIR}/{file_name}.raw",
                "wb",
            ) as file:
                file.write(file_data)
            _LOGGER.info(f"Saved image data from MQTT in {file_name}.raw!")

    @callback
    async def async_message_received(self, msg) -> None:
        """
        Handle new MQTT messages.
        MapData/map_data is for Hypfer, and map-data is for ValetudoRe.
        """
        self._rcv_topic = msg.topic
        if self._rcv_topic == f"{self._mqtt_topic}/map_data":
            if not self._data_in:
                _LOGGER.info(
                    f"Received Valetudo RE {self._mqtt_topic} image data from MQTT"
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
        elif (self._rcv_topic == f"{self._mqtt_topic}/MapData/map-data") and (not self._ignore_data):
            if not self._data_in:
                _LOGGER.info(f"Received {self._mqtt_topic} image data from MQTT")
                self._img_payload = msg.payload
                self._data_in = True
                self._is_rrm = False
        elif self._rcv_topic == f"{self._mqtt_topic}/StatusStateAttribute/status":
            self._payload = msg.payload
            if self._payload:
                self._mqtt_vac_stat = bytes.decode(self._payload, "utf-8")
                _LOGGER.info(
                    f"{self._mqtt_topic}: Received vacuum {self._mqtt_vac_stat} status."
                )
                if self._mqtt_vac_stat != "docked":
                    self._ignore_data = False
        elif self._rcv_topic == f"{self._mqtt_topic}/state":  # for ValetudoRe
            self._payload = msg.payload
            if self._payload:
                tmp_data = json.loads(self._payload)
                self._mqtt_vac_re_stat = tmp_data.get("state", None)
                _LOGGER.info(
                    f"{self._mqtt_topic}: Received vacuum {self._mqtt_vac_re_stat} status."
                )
        elif (
            self._rcv_topic
            == f"{self._mqtt_topic}/StatusStateAttribute/error_description"
        ):
            self._payload = msg.payload
            self._mqtt_vac_err = bytes.decode(msg.payload, "utf-8")
            _LOGGER.info(
                f"{self._mqtt_topic}: Received vacuum Error: {self._mqtt_vac_err}"
            )
        elif self._rcv_topic == f"{self._mqtt_topic}/destinations":
            self._payload = msg.payload
            tmp_data = bytes.decode(msg.payload, "utf-8")
            self._rrm_destinations = tmp_data
            _LOGGER.info(
                f"{self._mqtt_topic}: Received vacuum destinations: {self._rrm_destinations}"
            )

    async def async_subscribe_to_topics(self) -> None:
        """Subscribe to the MQTT topics for Hypfer and ValetudoRe."""
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

    async def rrm_publish_destinations(self) -> None:
        """
        Request the destinations from ValetudoRe.
        Destination is used to gater the room names.
        It also provides zones and points predefined in the ValetudoRe.
        """
        cust_payload = {"command": "get_destinations"}
        cust_payload = json.dumps(cust_payload)
        await mqtt.async_publish(
            self._hass,
            self._mqtt_topic + "/custom_command",
            cust_payload,
            _QOS,
            encoding="utf-8",
        )

    async def async_unsubscribe_from_topics(self) -> None:
        """Unsubscribe from all MQTT topics."""
        _LOGGER.debug("Unsubscribing topics!!!")
        map(lambda x: x(), self._unsubscribe_handlers)

    @staticmethod
    def get_test_payload(payload_data) -> None:
        """Test Payload for testing the Camera."""
        ValetudoConnector._img_payload = payload_data
        _LOGGER.debug("Processing Test Data..")
        ValetudoConnector._data_in = True

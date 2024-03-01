"""
Version 1.5.9-beta.1
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
        self._mqtt_vac_connect_state = ""
        self._mqtt_vac_battery_level = None
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
        self._file_name = camera_shared.file_name
        self._shared = camera_shared

    async def update_data(self, process: bool = True):
        """
        Update the data from MQTT.
        If it is a Valetudo RE, it will request the destinations.
        When the data is available, it will process it if the camera isn't busy.
        It simply unzips the data and returns the JSON.
        """
        payload = self._img_payload if self._img_payload else self._rrm_payload
        data_type = "Hypfer" if self._img_payload else "Rand256"
        if payload:
            if process:
                _LOGGER.debug(
                    f"{self._file_name}: Processing {data_type} data from MQTT."
                )
                if self._img_payload:
                    json_data = zlib.decompress(payload).decode("utf-8")
                    result = json.loads(json_data)
                else:
                    payload_decompressed = gzip.decompress(payload).decode("utf-8")
                    self._rrm_json = self._rrm_data.parse_data(
                        payload=payload_decompressed, pixels=True
                    )
                    result = self._rrm_json

                _LOGGER.info(
                    f"{self._file_name}: Extraction of {data_type} JSON Complete."
                )
                self._data_in = False
                self._is_rrm = bool(self._rrm_payload)
                return result, self._is_rrm
            else:
                _LOGGER.info(
                    f"No image data from {self._mqtt_topic},"
                    f"vacuum in { self._mqtt_vac_stat} status."
                )
                self._ignore_data = True
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

    async def get_battery_level(self) -> str:
        """Rerun vacuum battery Level."""
        return str(self._mqtt_vac_battery_level)

    async def get_vacuum_connection_state(self) -> bool:
        """Return the vacuum connection state."""
        if self._mqtt_vac_connect_state != "ready":
            return False
        return True

    async def get_destinations(self):
        """Return the destinations used only for Rand256."""
        return self._rrm_destinations

    async def is_data_available(self) -> bool:
        """Check and Return the data availability."""
        return self._data_in

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
        elif (self._rcv_topic == f"{self._mqtt_topic}/MapData/map-data") and (
            not self._ignore_data
        ):
            if not self._data_in:
                _LOGGER.info(f"Received {self._file_name} image data from MQTT")
                self._img_payload = msg.payload
                self._data_in = True
                self._is_rrm = False
        elif self._rcv_topic == f"{self._mqtt_topic}/StatusStateAttribute/status":
            self._payload = msg.payload
            if self._payload:
                self._mqtt_vac_stat = bytes.decode(self._payload, "utf-8")
                _LOGGER.info(
                    f"{self._file_name}: Received vacuum {self._mqtt_vac_stat} status."
                )
                if self._mqtt_vac_stat != "docked":
                    self._ignore_data = False
        elif self._rcv_topic == f"{self._mqtt_topic}/$state":
            self._payload = msg.payload
            if self._payload:
                self._mqtt_vac_connect_state = bytes.decode(self._payload, "utf-8")
                _LOGGER.info(
                    f"{self._mqtt_topic}: Received vacuum connection status: {self._mqtt_vac_connect_state}."
                )
            if self._ignore_data and self._mqtt_vac_connect_state != "ready":
                self._ignore_data = False
                self._data_in = True
        elif self._rcv_topic == f"{self._mqtt_topic}/BatteryStateAttribute/level":
            self._payload = msg.payload
            if self._payload:
                self._mqtt_vac_battery_level = int(bytes.decode(self._payload, "utf-8"))
                _LOGGER.info(
                    f"{self._file_name}: Received vacuum battery level: {self._mqtt_vac_battery_level }%."
                )
        elif self._rcv_topic == f"{self._mqtt_topic}/state":  # for ValetudoRe
            self._payload = msg.payload
            if self._payload:
                tmp_data = json.loads(self._payload)
                self._mqtt_vac_re_stat = tmp_data.get("state", None)
                self._mqtt_vac_battery_level = tmp_data.get("battery_level", None)
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
                f"{self._file_name}: Received vacuum destinations: {self._rrm_destinations}"
            )

    async def async_subscribe_to_topics(self) -> None:
        """Subscribe to the MQTT topics for Hypfer and ValetudoRe."""
        if self._mqtt_topic:
            for x in [
                self._mqtt_topic + "/MapData/map-data",
                self._mqtt_topic + "/StatusStateAttribute/status",
                self._mqtt_topic + "/StatusStateAttribute/error_description",
                self._mqtt_topic + "/$state",
                self._mqtt_topic + "/BatteryStateAttribute/level",
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

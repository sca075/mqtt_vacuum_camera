import logging
import paho.mqtt.client as client

from custom_components.valetudo_vacuum_camera.utils.valetudo_jdata import RawToJson

_LOGGER = logging.getLogger(__name__)


class ValetudoConnector(client.Client):
    def __init__(self, mqttusr, mqttpass, mqtt_topic, hass):
        super().__init__("valetudo_connector")
        self._mqtt_topic = mqtt_topic
        self._broker = "127.0.0.1"
        self.username_pw_set(username=mqttusr, password=mqttpass)
        self.on_connect = self.on_connect_callback
        self.on_message = self.on_message_callback
        self.connect_async(host=self._broker, port=1883)
        self.enable_bridge_mode()
        self.loop_start()
        self._payload = None
        self._data_in = False
        self._img_decoder = RawToJson(hass)

    def update_data(self):
        if self._payload:
            _LOGGER.debug("Processing data from MQTT")
            result = self._img_decoder.camera_message_received(self._payload)
            self._data_in = False
            return result
        else:
            _LOGGER.debug("No data from MQTT")
            self._data_in = False
            return None

    def is_data_available(self):
        return self._data_in

    def on_message_callback(self, client, userdata, msg):
        self._payload = msg.payload
        self._data_in = True
        _LOGGER.debug("Received data from MQTT")

    def on_connect_callback(self, client, userdata, flags, rc):
        self.subscribe(self._mqtt_topic)
        _LOGGER.debug("Connected to MQTT broker.")

    def stop_and_disconnect(self):
        self.loop_stop(force=False)  # Stop the MQTT loop gracefully
        self.disconnect()  # Disconnect from the broker
        _LOGGER.debug("Stopped and disconnected from MQTT broker.")

    def connect_broker(self):
        self.connect_async(host=self._broker, port=1883)
        self.enable_bridge_mode()
        self.loop_start()
        _LOGGER.debug("Connect MQTT broker.")

    def client_start(self):
        self.loop_start()
        _LOGGER.debug("Started MQTT loop")

    def client_stop(self):
        self.loop_stop()
        _LOGGER.debug("Stopped MQTT loop")

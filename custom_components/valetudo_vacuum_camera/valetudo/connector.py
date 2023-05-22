import logging
import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)


class ValetudoConnector:
    def __init__(self, mqtt_topic):
        self._mqtt_topic = mqtt_topic
        self._broker = "127.0.0.1"
        self._payload = None
        self._mqtt = mqtt.Client("valetudo_connector")
        self._mqtt.on_connect = self.on_connect
        self._mqtt.on_message = self.on_message
        self._mqtt.username_pw_set(username="MQTT_User", password="MQTT_Connect")
        self._mqtt.connect_async(host=self._broker)
        self._mqtt.enable_bridge_mode()
        self._mqtt.loop_start()

    def update_data(self, data):
        if data:
            return self._payload
        else:
            return None

    def on_message(self, client, userdata, msg):
        _LOGGER.debug("Received data from MQTT: %s", msg.payload)
        self._payload = msg.payload

    def on_connect(self, client, userdata, flags, rc):
        _LOGGER.debug("Connected to MQTT broker.")
        self._mqtt.subscribe(self._mqtt_topic)

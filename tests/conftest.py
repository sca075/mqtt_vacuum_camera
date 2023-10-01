"""pytest fixtures."""
# from version 1.4.x use internal broker

import logging

import pytest
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component import components
from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from custom_components.valetudo_vacuum_camera.const import DOMAIN
from custom_components.valetudo_vacuum_camera.camera import ValetudoConnector, ValetudoCamera

_LOGGER: logging.Logger = logging.getLogger(__name__)


def load_mqtt_topic_from_file(file_path):
    """Load MQTT topic from a file."""
    with open(file_path, 'rb') as file:
        return file.read().strip()

def vacuum_entity():
    data = {"name":"V1 TestVacuum",
            "object_id":"valetudo_testvacuum",
            "schema":"state",
            "supported_features":["battery","status","start","stop","pause","return_home","fan_speed","locate"],
            "state_topic":"valetudo/TestVacuum/hass/TestVacuum/state",
            "command_topic":"valetudo/TestVacuum/hass/TestVacuum/command",
            "payload_start":"START",
            "payload_pause":"PAUSE",
            "payload_return_to_base":"HOME",
            "payload_stop":"STOP",
            "payload_locate":"LOCATE",
            "fan_speed_list":["min","low","medium","high","max"],
            "set_fan_speed_topic":"valetudo/TestVacuum/FanSpeedControlCapability/preset/set",
            "unique_id":"TestVacuum_vacuum",
            "availability_topic":"valetudo/TestVacuum/$state",
            "payload_available":"ready",
            "payload_not_available":"lost",
            "device":{"manufacturer":"Roborock",
                      "model":"V1",
                      "name":"V1 TestVacuum",
                      "identifiers":["TestVacuum"],
                      "sw_version":"2023.08.0 (Valetudo)",
                      "configuration_url":"http://valetudo-testvacuum.local"}
            }
    return data


async def test_async_setup(hass):
    """Test the component get setup."""
    print("*** Setup Started ***")
    mqtt_payload = load_mqtt_topic_from_file("./tests/mqtt_data.raw")
    broker = mqtt.MQTT(hass, ConfigEntry, vacuum_entity())
    await broker.async_publish(topic="homeassistant/vacuum/TestVacuum/TestVacuum_vacuum/config",
                         payload=vacuum_entity(),
                         qos=0
                         )
    await broker.async_publish(topic="valetudo/TestVacuum/TestVacuum/status", payload="docked", qos=0)
    await broker.async_publish(topic="valetudo/TestVacuum/TestVacuum/error_description",
                         payload="No Error",
                         qos=0
                         )
    await broker.async_publish(topic="valetudo/TestVacuum/MapData/map-data-hass",
                         payload=mqtt_payload,
                         qos=0
                         )
    _LOGGER.debug(broker)
    assert await async_setup_component(hass, DOMAIN, {}) is True


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations defined in the test dir."""
    yield

'''test camera.py version 1.4.x'''

import socket
import time

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from custom_components.valetudo_vacuum_camera.utils.valetudo_jdata import RawToJson
from custom_components.valetudo_vacuum_camera.camera import ValetudoCamera
from homeassistant.components.camera import Camera

def load_mqtt_topic_from_file(file_path):
    """Load MQTT topic from a file."""
    with open(file_path, 'rb') as file:
        return file.read().strip()

def load_test_json(file_path):
    with open(file_path, "rb") as j_file:
        tmp_json = j_file.read()
    return tmp_json

@pytest.mark.asyncio
@pytest.mark.enable_socket
async def test_update_success(hass, aioclient_mock, socket_enabled, enable_custom_integrations):
    """Tests a fully successful async_update."""
    json_load = load_test_json("./tests/test.json")
    mqtt_data = load_mqtt_topic_from_file("./tests/mqtt_data.raw")


    camera = MagicMock()
    camera.getitem = AsyncMock(
        side_effect=[
            {
                "vacuum_entity": "vacuum.valetudo_testvacuum",
                "vacuum_map": "valetudo/TestVacuum"
            },
        ]
    )

    camera = ValetudoCamera(Camera, {"path": "homeassistant/core"})
    await camera.test_camera_scenario(json_load, mqtt_data)
    await camera.async_update()
    camera.throttled_camera_image()
    camera.camera_image()

    expected = {
        "vacuum_position": None,
        "friendly_name": "Camera",
        "calibration_points": None,
        "json_data": "Success",
        "vacuum_topic": "valetudo/TestVacuum",
        "snapshot": False,
        "snapshot_path": "/local/snapshot_" + "testvacuum" + ".png",
        "vacuum_json_id": None,
        "vacuum_status": "cleaning",
    }

    # assert socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # assert camera.available == True
    assert camera.state == "idle"
    assert expected == camera.extra_state_attributes
    assert camera.name == "Camera"

    # Assert that the MQTT topic is as expected
    # assert mqtt_topic == "valetudo/my_vacuum/MapData/map-data-hass"

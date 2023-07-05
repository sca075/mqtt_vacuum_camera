from unittest.mock import AsyncMock, MagicMock

# from tests.testsupport.broker import fake_websocket_broker, fake_broker
import pytest
import socket

from valetudo_vacuum_camera.camera import ValetudoCamera
from homeassistant.components.camera import Camera


@pytest.mark.allow_hosts(["127.0.0.1"], 1883)
@pytest.mark.asyncio
@pytest.mark.enable_socket
async def test_update_success(hass, aioclient_mock, socket_enabled):
    """Tests a fully successful async_update."""
    camera = MagicMock()
    camera.getitem = AsyncMock(
        side_effect=[
            # user response
            {
                "vacuum_entity": "vacuum.my_vacuum",
                "broker_user": "mqttUser",
                "broker_password": "mqttPassword",
                "vacuum_map": "valetudo/myTopic",
            }
        ]
    )
    camera = ValetudoCamera(Camera, {"path": "homeassistant/core"})
    camera.update()
    camera.turn_off()

    expected = {
        "calibration_points": None,
        "json_data": None,
        "listen_to": None,
        "robot_position": None,
        "vacuum_entity": None,
        "vacuum_json_id": None,
        "vacuum_status": None,
    }

    assert socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    assert camera.available is True
    assert camera.state == "idle"
    assert expected == camera.extra_state_attributes


@pytest.mark.allow_hosts(["127.0.0.1"])
@pytest.mark.asyncio
@pytest.mark.enable_socket
async def test_async_update_failed(socket_enabled):
    """Tests a failed async_update."""
    camera = MagicMock()
    camera.getitem = AsyncMock()

    camera = ValetudoCamera(Camera, {"path": "homeassistant/core"})
    camera.update()
    camera.turn_off()

    assert socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    assert camera.available == True
    assert camera.camera_image() == None

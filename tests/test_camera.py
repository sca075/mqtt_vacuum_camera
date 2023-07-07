from unittest.mock import AsyncMock, MagicMock
import socket
import pytest
from custom_components.valetudo_vacuum_camera.camera import ValetudoCamera
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
    camera.throttled_camera_image()
    camera.update()
    #camera.turn_off()


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
    #assert camera.camera_image() is not None

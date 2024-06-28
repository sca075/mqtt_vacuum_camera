import socket
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from custom_components.mqtt_vacuum_camera.camera import ValetudoCamera
from homeassistant.components.camera import Camera


@pytest.fixture
def mock_mqtt(hass, mqtt_mock):
    """Mock the MQTT component."""
    mqtt_mock().async_subscribe.return_value = AsyncMock()
    return mqtt_mock


def load_mqtt_topic_from_file(file_path):
    """Load MQTT topic from a file."""
    with open(file_path, "r") as file:
        return file.read().strip()


@pytest.mark.asyncio
@pytest.mark.enable_socket
async def test_update_success(
    hass, aioclient_mock, socket_enabled, enable_custom_integrations, mock_mqtt
):
    """Tests a fully successful async_update."""
    # Load MQTT topic from file
    mqtt_topic = load_mqtt_topic_from_file("tests/mqtt_data.raw")

    camera = MagicMock()
    camera.getitem = AsyncMock(
        side_effect=[
            {"vacuum_entity": "vacuum.my_vacuum", "vacuum_map": "valetudo/my_vacuum"},
        ]
    )

    with patch(
        "custom_components.mqtt_vacuum_camera.camera.ConfigFlowHandler.async_step_user",
        return_value={"title": "My Vacuum Camera"},
    ):
        camera = ValetudoCamera(Camera, {"path": "homeassistant/core"})
        camera.camera_image()

    expected = {
        "calibration_points": None,
        "json_data": None,
        "listen_to": None,
        "robot_position": None,
        "snapshot": None,
        "snapshot_path": "/local/snapshot_" + "my_vacuum" + ".png",
        "vacuum_json_id": None,
        "vacuum_status": None,
    }

    assert socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    assert camera.available is True
    assert camera.state == "idle"
    assert expected == camera.extra_state_attributes
    assert camera.name == "Camera"

    # Assert that the MQTT topic is as expected
    assert mqtt_topic == "valetudo/my_vacuum/MapData/map-data-hass"

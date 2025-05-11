"""pytest fixtures."""

import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.helpers.device_registry import DeviceEntry

from custom_components.mqtt_vacuum_camera.const import DOMAIN, CameraModes


async def test_async_setup(hass):
    """Test the component get setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations defined in the test dir."""
    yield


@pytest.fixture
def mock_hass():
    """Mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config.path.return_value = "/config"
    return hass


@pytest.fixture
def mock_device_entry_hypfer():
    """Mock device entry for Hypfer firmware."""
    device = MagicMock(spec=DeviceEntry)
    device.sw_version = "Valetudo 2023.01.0"
    return device


@pytest.fixture
def mock_device_entry_rand256():
    """Mock device entry for Rand256 firmware."""
    device = MagicMock(spec=DeviceEntry)
    device.sw_version = "RandoFirmware 1.0"
    return device


@pytest.fixture
def hypfer_sample_data():
    """Load Hypfer sample data."""
    with open("tests/json_samples/hypfer_sample.json", "r") as f:
        return json.load(f)


@pytest.fixture
def rand256_sample_data():
    """Load Rand256 sample data."""
    with open("tests/json_samples/rand256_sample.json", "r") as f:
        return json.load(f)


@pytest.fixture
def mock_shared_data():
    """Mock shared data object."""
    shared = MagicMock()
    shared.camera_mode = CameraModes.MAP_VIEW
    shared.file_name = "test_vacuum"
    shared.is_rand = False
    shared.image_grab = False
    shared.snapshot_take = False
    shared.enable_snapshots = False
    shared.reload_config = False
    shared.obstacle_view = False
    shared.obstacle_x = 0
    shared.obstacle_y = 0
    shared.destinations = []
    shared.disable_floor = False
    shared.disable_wall = False
    shared.disable_robot = False
    shared.disable_charger = False
    shared.disable_path = False
    shared.disable_segments = False
    shared.disable_no_go_areas = False
    shared.disable_no_mop_areas = False
    shared.disable_virtual_walls = False
    shared.disable_obstacles = False
    return shared

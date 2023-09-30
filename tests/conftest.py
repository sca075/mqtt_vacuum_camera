"""pytest fixtures."""
# from version 1.4.x use internal broker

import logging
import pytest
from homeassistant.setup import async_setup_component
from homeassistant.components import mqtt, http, file_upload
from custom_components.valetudo_vacuum_camera.const import DOMAIN
from unittest.mock import AsyncMock, MagicMock, patch

_LOGGER: logging.Logger = logging.getLogger(__name__)

@pytest.fixture(autouse=True)
def mock_mqtt(hass, mqtt_mock):
    """Mock the MQTT component."""
    mqtt_mock().async_subscribe.return_value = AsyncMock()
    return mqtt_mock

async def test_async_setup(hass):
    """Test the component get setup."""
    print("*** Setup Started ***")
    _LOGGER.debug(mqtt.ConfigEntry.data)
    assert await async_setup_component(hass, DOMAIN, {}) is True


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations defined in the test dir."""
    yield

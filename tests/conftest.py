"""pytest fixtures."""
import pytest
from homeassistant.setup import async_setup_component
# from homeassistant.components import mqtt
from custom_components.valetudo_vacuum_camera.const import DOMAIN


async def test_async_setup(hass):
    """Test the component get setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations defined in the test dir."""
    yield

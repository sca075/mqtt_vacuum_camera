"""Tests for the component setup."""

from homeassistant.setup import async_setup_component

from custom_components.mqtt_vacuum_camera.const import DOMAIN


async def test_async_setup(hass, mqtt_mock):
    """Test the component get setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True

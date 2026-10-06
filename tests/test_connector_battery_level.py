"""Tests for ValetudoConnector.get_battery_level() with missing MQTT data."""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.mqtt_vacuum_camera.utils.connection.connector import (
    ValetudoConnector,
)


def _make_connector():
    """Build a ValetudoConnector with minimal mocks."""
    hass = MagicMock()
    hass.async_create_task = MagicMock()

    shared = MagicMock()
    shared.file_name = "test_vacuum"
    shared.camera_mode = MagicMock()

    with patch(
        "custom_components.mqtt_vacuum_camera.utils.connection.connector.RoomStore"
    ):
        connector = ValetudoConnector(
            mqtt_topic="valetudo/TestRobot",
            hass=hass,
            camera_shared=shared,
        )

    return connector


@pytest.mark.asyncio
async def test_get_battery_level_returns_zero_when_no_data():
    """No battery data yet (e.g. vacuum offline) must not become the string 'None'."""
    connector = _make_connector()
    connector.mqtt_data.mqtt_vac_battery_level = None

    result = await connector.get_battery_level()

    assert result == "0"
    assert int(result) == 0  # this is what valetudo_map_parser does with it


@pytest.mark.asyncio
async def test_get_battery_level_returns_value_when_present():
    """A real battery level is still passed through unchanged."""
    connector = _make_connector()
    connector.mqtt_data.mqtt_vac_battery_level = 87

    result = await connector.get_battery_level()

    assert result == "87"

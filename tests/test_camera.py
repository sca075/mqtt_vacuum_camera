"""Tests for the sensor module."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.valetudo_vacuum_camera.camera import ValetudoCamera
from homeassistant.components.camera import (Camera)


@pytest.mark.asyncio
async def test_async_update_success(hass, aioclient_mock):
    """Tests a fully successful async_update."""
    camera = MagicMock()
    camera.getitem = AsyncMock(
        side_effect=[
            # user response
            {
                "vacuum_entity": None,
                "broker_user": None,
                "broker_password": None,
                "vacuum_map": None,
            }]
    )
    camera = ValetudoCamera(Camera,{"path": "homeassistant/core"})
    await camera.async_update()

    expected = {
        "vacuum_entity": "vacuum.my_vacuum",
        "broker_user": "mqttUser",
        "broker_password": "mqttPassword",
        "vacuum_map": "valetudo/myTopic",
    }

    assert expected == camera.attrs
    assert expected == camera.extra_state_attributes
    assert camera.available is True


@pytest.mark.asyncio
async def test_async_update_failed():
    """Tests a failed async_update."""
    camera = MagicMock()
    camera.getitem = AsyncMock()

    camera = ValetudoCamera(Camera, {"path": "homeassistant/core"})

    await camera.async_update()

    assert camera.available is False
    assert {"path": "homeassistant/core"} == camera._attr_state
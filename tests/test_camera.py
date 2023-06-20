"""Tests for the sensor module."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.valetudo_vacuum_camera.camera import ValetudoCamera
from homeassistant.components.camera import (Camera)


@pytest.mark.asyncio
async def test_async_update_success(hass, aioclient_mock):
    """Tests a fully successful async_update."""
    camera = MagicMock()
    camera.getitem = AsyncMock()
    camera = ValetudoCamera(Camera, aioclient_mock)
    await camera.async_update()

    expected = {
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
    assert {"path": "homeassistant/core"} == camera.attrs
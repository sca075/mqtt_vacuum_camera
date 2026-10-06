"""Tests for the image format default in get_camera_device_info()."""

from unittest.mock import MagicMock

import pytest

from custom_components.mqtt_vacuum_camera.common import get_camera_device_info
from custom_components.mqtt_vacuum_camera.const import DEFAULT_VALUES


def _hass_with_entry(data, options):
    """Return a mocked hass whose config entry has the given data and options."""
    entry = MagicMock()
    entry.data = data
    entry.options = options
    hass = MagicMock()
    hass.config_entries.async_get_entry.return_value = entry
    return hass


@pytest.mark.parametrize(
    "options, expected",
    [
        ({}, "jpeg"),  # key missing (fresh entry)
        ({"def_context_type": None}, "jpeg"),  # stored as None by the options flow
        ({"def_context_type": ""}, "jpeg"),
        ({"def_context_type": "png"}, "png"),  # an explicit choice is kept
        ({"def_context_type": "jpeg"}, "jpeg"),
    ],
)
def test_def_context_type_default(options, expected):
    """A missing or empty image format falls back to jpeg; a real one is kept."""
    hass = _hass_with_entry({"unique_id": "test_camera"}, options)
    entry = MagicMock()
    entry.entry_id = "abc"

    result = get_camera_device_info(hass, entry)

    assert result["def_context_type"] == expected


def test_default_values_include_image_format():
    """update_options() falls back to DEFAULT_VALUES, so it must define the format."""
    assert DEFAULT_VALUES["def_context_type"] == "jpeg"

"""Tests for the MQTT Vacuum Camera config flow."""

from unittest import mock
from unittest.mock import patch

from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mqtt_vacuum_camera import config_flow
from custom_components.mqtt_vacuum_camera.const import (
    CONF_VACUUM_CONFIG_ENTRY_ID,
    DEFAULT_VALUES,
)

VACUUM_ENTITY_ID = "vacuum.test_robot"
VACUUM_MQTT_TOPIC = "valetudo/TestRobot"
VACUUM_UNIQUE_ID = "testrobot_camera"


@pytest.fixture
def vacuum_user_input():
    """Return the user input of the first config flow step."""
    return {config_flow.CONF_VACUUM_ENTITY_ID: VACUUM_ENTITY_ID}


@pytest.fixture
def vacuum_registry_entry(hass):
    """Register a vacuum device and entity in the Home Assistant registries."""
    mqtt_entry = MockConfigEntry(domain="mqtt")
    mqtt_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=mqtt_entry.entry_id,
        identifiers={("mqtt", "test_robot")},
        name="Test Robot",
    )
    return er.async_get(hass).async_get_or_create(
        "vacuum",
        "mqtt",
        "test_robot_unique_id",
        suggested_object_id="test_robot",
        device_id=device.id,
    )


async def test_flow_user_init(hass):
    """Test the initialization of the form for step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["flow_id"] == mock.ANY
    assert result["handler"] == config_flow.DOMAIN
    assert result["data_schema"] == config_flow.VACUUM_SCHEMA
    assert result["errors"] is None


async def test_flow_user_creates_config_entry(
    hass, vacuum_user_input, vacuum_registry_entry
):
    """Test the config entry is successfully created."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    with patch.object(
        config_flow, "get_vacuum_mqtt_topic", return_value=VACUUM_MQTT_TOPIC
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=vacuum_user_input
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Robot Camera"
    entries = hass.config_entries.async_entries(config_flow.DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_VACUUM_CONFIG_ENTRY_ID] == vacuum_registry_entry.id
    assert entries[0].data[CONF_UNIQUE_ID] == VACUUM_UNIQUE_ID
    assert entries[0].options == DEFAULT_VALUES


async def test_flow_user_aborts_when_already_configured(
    hass, vacuum_user_input, vacuum_registry_entry
):
    """Test a vacuum with an existing camera entry is rejected."""
    MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={CONF_UNIQUE_ID: VACUUM_UNIQUE_ID},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    with patch.object(
        config_flow, "get_vacuum_mqtt_topic", return_value=VACUUM_MQTT_TOPIC
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=vacuum_user_input
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

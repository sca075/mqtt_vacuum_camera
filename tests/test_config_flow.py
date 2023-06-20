"""Tests for the config flow."""
from unittest import mock
from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_NAME, CONF_PATH
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.valetudo_vacuum_camera import config_flow
from custom_components.valetudo_vacuum_camera.const import  CONF_VACUUM_ENTITY_ID, \
    CONF_MQTT_USER, \
    CONF_MQTT_PASS, \
    CONF_VACUUM_CONNECTION_STRING


@pytest.mark.asyncio
async def test_flow_user_init(hass):
    """Test the initialization of the form for step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    expected ={
        "data_schema": config_flow.AUTH_SCHEMA,
        "description_placeholders": None,
        "errors": None,
        "flow_id": mock.ANY,
        "handler": "valetudo_vacuum_camera",
        "last_step": None,
        "step_id": "user",
        "type": "form",
    }
    assert expected == result


@pytest.mark.asyncio
async def test_flow_user_init_form(hass):
    """Test the initialization of the form in the second step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    expected = {
        "data_schema": config_flow.AUTH_SCHEMA,
        "description_placeholders": None,
        "errors": None,
        "flow_id": mock.ANY,
        "handler": "valetudo_vacuum_camera",
        "step_id": "user",
        "last_step": None,
        "type": "form",
    }
    assert expected == result


@pytest.mark.asyncio
@patch("custom_components.valetudo_vacuum_camera.config_flow")
async def test_flow_user_creates_config_entry(user_input, hass):
    """Test the config entry is successfully created."""
    m_instance = AsyncMock()
    m_instance.getitem = AsyncMock()
    user_input.return_value = m_instance
    config_flow.ValetudoCameraFlowHandler.data = {
        "name": user_input.get(CONF_NAME),
        "vacuum_entity": user_input.get(CONF_VACUUM_ENTITY_ID),
        "broker_user": user_input.get(CONF_MQTT_USER),
        "broker_password": user_input.get(CONF_MQTT_PASS),
        "vacuum_map": user_input.get(CONF_VACUUM_CONNECTION_STRING)
    }
    with patch("custom_components.valetudo_vacuum_camera.async_setup_entry", return_value=True):
        _result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}
        )
        await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(
        _result["flow_id"],
        user_input={CONF_VACUUM_ENTITY_ID: "Vacuum Entity ID",
        CONF_MQTT_USER: "MQTT User Name",
        CONF_MQTT_PASS: "MQTT User Password",
        CONF_VACUUM_CONNECTION_STRING: "Vacuum Topic Prefix/Identifier"},
    )
    expected = {
        "context": {"source": "user"},
        "version": 1,
        "type": "create_entry",
        "flow_id": mock.ANY,
        "handler": "valetudo_vacuum_camera",
        "title": "valetudo vacuum camera",
        "data": {
            "vacuum_entity": "Vacuum Entity ID",
            "broker_user": "MQTT User Name",
            "broker_password": "MQTT User Password",
            "vacuum_map": "Vacuum Topic Prefix/Identifier"
        },
        "description": None,
        "description_placeholders": None,
        "options": {},
        "result": mock.ANY,
    }
    assert expected == result

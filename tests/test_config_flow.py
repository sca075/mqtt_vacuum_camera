import pytest
from unittest import mock
from unittest.mock import patch
from homeassistant.config_entries import ConfigEntry
from custom_components.valetudo_vacuum_camera import config_flow

@pytest.fixture
def vacuum_user_input():
    return {
        config_flow.CONF_VACUUM_ENTITY_ID: "Vacuum Entity ID",
    }

@pytest.fixture
def mqtt_user_input():
    return {
        config_flow.CONF_MQTT_USER: "MQTT User Name",
        config_flow.CONF_MQTT_PASS: "MQTT User Password",
        config_flow.CONF_VACUUM_CONNECTION_STRING: "Vacuum Topic Prefix/Identifier",
    }

@pytest.fixture
def options_user_input():
    return {
        config_flow.ATT_ROTATE: "Image Rotation",
        config_flow.ATT_CROP: "Crop Image",
    }



async def test_flow_user_init(hass):
    """Test the initialization of the form for step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    expected = {
        "data_schema": config_flow.VACUUM_SCHEMA,
        "description_placeholders": None,
        "errors": None,
        "flow_id": mock.ANY,
        "handler": config_flow.ValetudoCameraFlowHandler,
        "last_step": None,
        "step_id": "user",
        "type": "form",
    }
    assert expected == result



async def test_flow_mqtt(hass, vacuum_user_input):
    """Test the initialization of the form for MQTT step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    expected = {
        "data_schema": config_flow.MQTT_SCHEMA,
        "description_placeholders": None,
        "errors": None,
        "flow_id": mock.ANY,
        "handler": config_flow.ValetudoCameraFlowHandler,
        "last_step": None,
        "step_id": "mqtt",
        "type": "form",
    }
    assert expected == result


async def test_flow_options(hass, mqtt_user_input):
    """Test the initialization of the form for Options step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    expected = {
        "data_schema": config_flow.OPTIONS_SCHEMA,
        "description_placeholders": mqtt_user_input,
        "errors": None,
        "flow_id": mock.ANY,
        "handler": config_flow.ValetudoCameraFlowHandler,
        "last_step": None,
        "step_id": "options",
        "type": "form",
    }
    assert expected == result


async def test_flow_user_creates_config_entry(hass, vacuum_user_input, mqtt_user_input, options_user_input):
    """Test the config entry is successfully created."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={**vacuum_user_input, **mqtt_user_input, **options_user_input}
    )
    await hass.async_block_till_done()

    # Retrieve the created entry and verify data
    entries = hass.config_entries.async_entries(config_flow.DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {
        "vacuum_entity": "Vacuum Entity ID",
        "broker_user": "MQTT User Name",
        "broker_password": "MQTT User Password",
        "vacuum_map": "Vacuum Topic Prefix/Identifier",
        "rotate_image": "Image Rotation",
        "crop_image": "Crop Image",
    }

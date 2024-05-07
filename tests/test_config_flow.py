import pytest

# from homeassistant import config_entries, core
from custom_components.valetudo_vacuum_camera import config_flow

# from unittest.mock import patch
from unittest import mock


@pytest.fixture
def vacuum_user_input():
    return {
        config_flow.CONF_VACUUM_ENTITY_ID: "vacuum.entity_id",
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


async def test_flow_user_creates_config_entry(hass, vacuum_user_input):
    """Test the config entry is successfully created."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**vacuum_user_input},
    )
    await hass.async_block_till_done()

    # Retrieve the created entry and verify data
    entries = hass.config_entries.async_entries(config_flow.DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {
        "vacuum_entity": "vacuum.entity_id",
    }

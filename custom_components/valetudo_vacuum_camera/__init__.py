"""valetudo vacuum camera"""
import logging

from homeassistant import config_entries, core
from homeassistant.components import mqtt
from homeassistant.const import CONF_UNIQUE_ID, Platform
from homeassistant.exceptions import ConfigEntryNotReady
from .const import (
    CONF_MQTT_HOST,
    CONF_MQTT_USER,
    CONF_MQTT_PASS,
    CONF_VACUUM_CONNECTION_STRING,
    CONF_VACUUM_CONFIG_ENTRY_ID,
    CONF_VACUUM_IDENTIFIERS,
    DOMAIN,
)
from .common import (
    get_entity_identifier_from_mqtt,
    get_device_info,
    get_vacuum_mqtt_topic,
    get_vacuum_unique_id_from_mqtt_topic,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CAMERA]


async def options_update_listener(
        hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_migrate_entry(hass, config_entry: config_entries.ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1.2:
        new_data = {**config_entry.data}
        _LOGGER.debug(new_data)
        new_data.update({"trim_top": "0"})
        new_data.update({"trim_bottom": "0"})
        new_data.update({"trim_left": "0"})
        new_data.update({"trim_right": "0"})
        new_data.update({"show_vac_status": False})
        new_data.update({"color_text": [255, 255, 255]})
        _LOGGER.debug(new_data)
        new_options = {**config_entry.options}
        _LOGGER.debug(new_options)
        if new_options or len(new_options) > 0:
            new_options.update({"trim_top": "0"})
            new_options.update({"trim_bottom": "0"})
            new_options.update({"trim_left": "0"})
            new_options.update({"trim_right": "0"})
            new_options.update({"show_vac_status": False})
            new_options.update({"color_text": [255, 255, 255]})
        else:
            new_options = new_data
        _LOGGER.debug(new_options)

        config_entry.version = 1.3
        hass.config_entries.async_update_entry(config_entry, data=new_data)
        hass.config_entries.async_update_entry(config_entry, options=new_options)

    if config_entry.version == 1.3:
        new_data = {**config_entry.data}
        _LOGGER.debug(new_data)
        new_data.update({"broker_host": "core-mosquitto"})
        _LOGGER.debug(new_data)
        new_options = {**config_entry.options}
        _LOGGER.debug(new_options)
        if new_options or len(new_options) > 0:
            new_options.update({"broker_host": "core-mosquitto"})
        else:
            new_options = new_data
        _LOGGER.debug(new_options)

        config_entry.version = 1.4
        hass.config_entries.async_update_entry(config_entry, data=new_data)
        hass.config_entries.async_update_entry(config_entry, options=new_options)

    if config_entry.version < 2:
        new_data = {**config_entry.data}
        new_data.pop(CONF_MQTT_HOST, None)
        new_data.pop(CONF_MQTT_USER, None)
        new_data.pop(CONF_MQTT_PASS, None)

        mqtt_topic_base = new_data.pop(CONF_VACUUM_CONNECTION_STRING, None)
        if not mqtt_topic_base:
            _LOGGER.error(
                "Unable to migrate to version 2.0. Could not find %s. Please delete and recreate this entry.",
                CONF_VACUUM_CONNECTION_STRING,
            )
            return False

        mqtt_identifier = mqtt_topic_base.split("/")[1]
        config_entry_id = get_entity_identifier_from_mqtt(mqtt_identifier, hass)
        if not config_entry_id:
            _LOGGER.error(
                "Unable to migrate to version 2.0. Could not find a device for %s. Please delete and recreate this entry.",
                mqtt_topic_base,
            )
            return False
        new_data.update(
            {
                CONF_VACUUM_CONFIG_ENTRY_ID: config_entry_id,
                CONF_UNIQUE_ID: get_vacuum_unique_id_from_mqtt_topic(mqtt_topic_base),
            }
        )

        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, data=new_data)

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True


async def async_setup_entry(
        hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(entry.data)

    vacuum_entity_id, vacuum_device = get_device_info(
        hass_data[CONF_VACUUM_CONFIG_ENTRY_ID], hass
    )

    if not vacuum_entity_id:
        raise ConfigEntryNotReady(
            "Unable to lookup vacuum's entity ID. Was it removed?"
        )

    mqtt_topic_vacuum = get_vacuum_mqtt_topic(vacuum_entity_id, hass)
    if not mqtt_topic_vacuum:
        raise ConfigEntryNotReady("MQTT was not ready yet, automatically retrying")

    hass_data.update(
        {
            CONF_VACUUM_CONNECTION_STRING: "/".join(mqtt_topic_vacuum.split("/")[:-1]),
            CONF_VACUUM_IDENTIFIERS: vacuum_device.identifiers,
        }
    )

    # Registers update listener to update config entry when options are updated.
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)
    # Store a reference to the unsubscribe function to clean up if an entry is unloaded.
    hass_data["unsub_options_update_listener"] = unsub_options_update_listener
    hass.data[DOMAIN][entry.entry_id] = hass_data

    # Forward the setup to the camera platform.
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "camera")
    )
    return True


async def async_unload_entry(
        hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Remove config entry from domain.
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        entry_data["unsub_options_update_listener"]()

    return unload_ok


async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    """Set up the Valetudo Camera Custom component from yaml configuration."""
    # Make sure MQTT integration is enabled and the client is available
    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration is not available")
        return False
    hass.data.setdefault(DOMAIN, {})
    return True

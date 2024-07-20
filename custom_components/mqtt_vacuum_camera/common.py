"""
Common functions for the MQTT Vacuum Camera integration.
Version: 2024.07.4
"""

from __future__ import annotations

import logging
import re

from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .const import KEYS_TO_UPDATE
from .hass_types import GET_MQTT_DATA

_LOGGER = logging.getLogger(__name__)


def get_device_info(
    config_entry_id: str, hass: HomeAssistant
) -> tuple[str, DeviceEntry] | None:
    """
    Fetches the vacuum's entity ID and Device from the
    entity registry and device registry.
    """
    vacuum_entity_id = er.async_resolve_entity_id(er.async_get(hass), config_entry_id)
    if not vacuum_entity_id:
        _LOGGER.error("Unable to lookup vacuum's entity ID. Was it removed?")
        return None

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    vacuum_device = device_registry.async_get(
        entity_registry.async_get(vacuum_entity_id).device_id
    )
    if not vacuum_device:
        _LOGGER.error("Unable to locate vacuum's device ID. Was it removed?")
        return None

    return vacuum_entity_id, vacuum_device


def get_entity_identifier_from_mqtt(
    mqtt_identifier: str, hass: HomeAssistant
) -> str | None:
    """
    Fetches the vacuum's entity_registry id from the mqtt topic identifier.
    Returns None if it cannot be found.
    """
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(MQTT_DOMAIN, mqtt_identifier)}
    )
    entities = er.async_entries_for_device(entity_registry, device_id=device.id)
    for entity in entities:
        if entity.domain == VACUUM_DOMAIN:
            return entity.id

    return None


def get_vacuum_mqtt_topic(vacuum_entity_id: str, hass: HomeAssistant) -> str | None:
    """
    Fetches the mqtt topic identifier from the MQTT integration. Returns None if it cannot be found.
    """
    try:
        return list(
            hass.data[GET_MQTT_DATA]
            .debug_info_entities.get(vacuum_entity_id)
            .get("subscriptions")
            .keys()
        )[0]
    except AttributeError:
        return None


def get_vacuum_unique_id_from_mqtt_topic(vacuum_mqtt_topic: str) -> str:
    """
    Returns the unique_id computed from the mqtt_topic for the vacuum.
    """
    return vacuum_mqtt_topic.split("/")[1].lower() + "_camera"


async def update_options(bk_options, new_options):
    """
    Keep track of the modified options.
    Returns updated options after editing in Config_Flow.
    """
    # Initialize updated_options as an empty dictionary
    # updated_options = {}
    keys_to_update = KEYS_TO_UPDATE
    try:
        updated_options = {
            key: new_options[key] if key in new_options else bk_options[key]
            for key in keys_to_update
        }
    except KeyError as e:
        _LOGGER.warning(f"Error in migrating options, please re-setup the camera: {e}")
        return bk_options
    # updated_options is a dictionary containing the merged options
    updated_bk_options = updated_options  # or backup_options, as needed
    return updated_bk_options


def extract_file_name(unique_id: str) -> str:
    """Extract from the Camera unique_id the file name."""
    file_name = re.sub(r"_camera$", "", unique_id)
    return file_name.lower()

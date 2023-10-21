from __future__ import annotations

import logging
import json

from homeassistant.core import HomeAssistant
from homeassistant.components import mqtt
from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

_LOGGER: logging.Logger = logging.getLogger(__name__)


def get_device_info(config_entry_id: str, hass: HomeAssistant) -> tuple[str, DeviceEntry] | None:
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
            mqtt.get_mqtt_data(hass)
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
    return vacuum_mqtt_topic.split("/")[1] + "_camera"


def update_options(bk_options, new_options):
    """
    Keep track of the modified options.
    Returns updated options after edit in Config_Flow.
    """
    current_options = json.loads(new_options)
    backup_options = json.loads(bk_options)
    keys_to_update = ['rotate_image', 'crop_image', 'trim_top', 'trim_bottom', 'trim_left', 'trim_right',
                      'show_vac_status', 'enable_www_snapshots', 'color_charger', 'color_move', 'color_wall',
                      'color_robot', 'color_go_to', 'color_no_go', 'color_zone_clean', 'color_background',
                      'color_text']
    for key in keys_to_update:
        if key in current_options:
            backup_options[key] = current_options[key]
    alpha_keys = [f'alpha_{obj}' for obj in keys_to_update]
    for alpha_key in alpha_keys:
        if alpha_key in current_options:
            backup_options[alpha_key] = current_options[alpha_key]

    updated_bk_options = json.dumps(backup_options)

    return updated_bk_options

from __future__ import annotations

import logging

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


async def update_options(bk_options, new_options):
    """
    Keep track of the modified options.
    Returns updated options after editing in Config_Flow.
    """
    # Initialize updated_options as an empty dictionary
    updated_options = {}

    keys_to_update = ['rotate_image', 'crop_image', 'trim_top', 'trim_bottom', 'trim_left', 'trim_right',
                      'show_vac_status', 'enable_www_snapshots', 'color_charger', 'color_move', 'color_wall',
                      'color_robot', 'color_go_to', 'color_no_go', 'color_zone_clean', 'color_background',
                      'color_text', 'alpha_charger', 'alpha_move', 'alpha_wall', 'alpha_robot', 'alpha_go_to',
                      'alpha_no_go', 'alpha_zone_clean', 'alpha_background', 'alpha_text', 'color_room_0',
                      'color_room_1', 'color_room_2', 'color_room_3', 'color_room_4', 'color_room_5', 'color_room_6',
                      'color_room_7', 'color_room_8', 'color_room_9', 'color_room_10', 'color_room_11', 'color_room_12',
                      'color_room_13', 'color_room_14', 'color_room_15', 'alpha_room_0', 'alpha_room_1',
                      'alpha_room_2', 'alpha_room_3', 'alpha_room_4', 'alpha_room_5', 'alpha_room_6', 'alpha_room_7',
                      'alpha_room_8', 'alpha_room_9', 'alpha_room_10', 'alpha_room_11', 'alpha_room_12',
                      'alpha_room_13', 'alpha_room_14', 'alpha_room_15']

    for key in keys_to_update:
        if key in new_options:
            updated_options[key] = new_options[key]
        else:
            updated_options[key] = bk_options[key]
    # updated_options is a dictionary containing the merged options
    updated_bk_options = updated_options  # or backup_options, as needed
    return updated_bk_options

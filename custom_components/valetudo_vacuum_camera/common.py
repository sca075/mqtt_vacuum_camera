"""
Common functions for the Valetudo Vacuum Camera integration.
Version: 2024.06.4
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import KEYS_TO_UPDATE
from .hass_types import GET_MQTT_DATA

_LOGGER: logging.Logger = logging.getLogger(__name__)


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


async def async_load_file(file_to_load: str, is_json: bool = False) -> Any:
    """Asynchronously load JSON data from a file."""
    loop = asyncio.get_event_loop()

    def read_file(my_file: str, read_json: bool = False):
        """Helper function to read data from a file."""
        try:
            if read_json:
                with open(my_file) as file:
                    return json.load(file)
            else:
                with open(my_file) as file:
                    return file.read()
        except (FileNotFoundError, json.JSONDecodeError):
            _LOGGER.warning(f"{my_file} does not exist.")
            return None

    try:
        return await loop.run_in_executor(None, read_file, file_to_load, is_json)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        _LOGGER.warning(f"Blocking IO issue detected: {e}")
        return None


async def async_write_json_to_disk(file_to_write: str, json_data) -> None:
    """Asynchronously write data to a JSON file."""
    loop = asyncio.get_event_loop()

    def _write_to_file(file_path, data):
        """Helper function to write data to a file."""
        with open(file_path, "w") as datafile:
            json.dump(data, datafile, indent=2)

    try:
        await loop.run_in_executor(None, _write_to_file, file_to_write, json_data)
    except OSError as e:
        _LOGGER.warning(f"Blocking issue detected: {e}")


async def async_write_file_to_disk(
    file_to_write: str, data, is_binary: bool = False
) -> None:
    """Asynchronously write data to a file."""
    loop = asyncio.get_event_loop()

    def _write_to_file(file_path, data_to_write, binary_mode):
        """Helper function to write data to a file."""
        if binary_mode:
            with open(file_path, "wb") as datafile:
                datafile.write(data_to_write)
        else:
            with open(file_path, "w") as datafile:
                datafile.write(data_to_write)

    try:
        await loop.run_in_executor(None, _write_to_file, file_to_write, data, is_binary)
    except OSError as e:
        _LOGGER.warning(f"Blocking issue detected: {e}")

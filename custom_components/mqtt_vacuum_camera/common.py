"""
Common functions for the MQTT Vacuum Camera integration.
Version: 2024.11.0
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


def get_vacuum_device_info(
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


def get_camera_device_info(hass, entry):
    """Fetch the device info from the device registry based on entry_id or identifier."""
    camera_entry = dict(hass.config_entries.async_get_entry(str(entry.entry_id)).data)
    camera_entry_options = dict(
        hass.config_entries.async_get_entry(str(entry.entry_id)).options
    )
    camera_entry.update(camera_entry_options)
    return camera_entry


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
        # Get the first subscription topic
        full_topic = list(
            hass.data[GET_MQTT_DATA]
            .debug_info_entities.get(vacuum_entity_id)
            .get("subscriptions")
            .keys()
        )[0]

        # Split and remove the last part after the last "/"
        topic_parts = full_topic.split("/")
        base_topic = "/".join(topic_parts[:-1])
        return str(base_topic)
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


def is_rand256_vacuum(vacuum_device: DeviceEntry) -> bool:
    """
    Check if the vacuum is running Rand256 firmware.
    """
    # Check if the software version contains "valetudo" (for Hypfer) or something else for Rand256
    sof_version = str(vacuum_device.sw_version)
    if (sof_version.lower()).startswith("valetudo"):
        _LOGGER.debug("No Sensors to startup!")
        return False  # This is a Hypfer vacuum (Valetudo)
    return True


def build_full_topic_set(
    base_topic: str, topic_suffixes: set, add_topic: str = None
) -> set:
    """
    Append the base topic (self._mqtt_topic) to a set of topic suffixes.
    Optionally, add a single additional topic string.
    Returns a set of full MQTT topics.
    """
    # Build the set of full topics from the topic_suffixes
    full_topics = {f"{base_topic}{suffix}" for suffix in topic_suffixes}

    # If add_topic is provided, add it to the set
    if add_topic:
        full_topics.add(add_topic)

    return full_topics


def from_device_ids_to_entity_ids(device_ids: str, hass: HomeAssistant) -> str:
    """
    Convert a device_id to an entity_id.
    """
    # Resolve device_id to entity_id using Home Assistant’s device and entity registries
    dev_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)
    resolved_entity_ids = []

    for device_id in device_ids:
        # Look up device by device_id
        device = dev_reg.async_get(device_id)
        if device:
            # Find all entities linked to this device_id in the vacuum domain
            for entry in entity_reg.entities.values():
                if entry.device_id == device_id and entry.domain == "vacuum":
                    resolved_entity_ids.append(entry.entity_id)
            return resolved_entity_ids


def get_device_info_from_entity_id(entity_id: str, hass) -> DeviceEntry:
    """
    Fetch the device info from the device registry based on entity_id.
    """
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)
    for entry in entity_reg.entities.values():
        if entry.entity_id == entity_id and entry.domain == "vacuum":
            device_id = entry.device_id
            device = device_reg.async_get(device_id)
            return device


def get_entity_id(
    entity_id: str | None, device_id: str | None, hass: HomeAssistant
) -> str | None:
    """Resolve the Vacuum Entity ID"""
    vacuum_entity_id = entity_id  # Default to entity_id
    if device_id:
        resolved_entities = from_device_ids_to_entity_ids(device_id, hass)
        vacuum_entity_id = resolved_entities
    elif not vacuum_entity_id:
        _LOGGER.error(f"No vacuum entities found for device_id: {device_id}")
        return None
    return vacuum_entity_id


def generate_service_data_go_to(
    entity_id: str | None,
    device_id: str | None,
    x: int = None,
    y: int = None,
    spot_id: str = None,
    hass: HomeAssistant = None,
) -> dict | None:
    """
    Generates the data necessary for sending the service go_to point to the vacuum.
    """
    # Resolve entity ID if only device ID is given
    vacuum_entity_id = get_entity_id(entity_id, device_id, hass)[0]

    # Get the vacuum topic and check firmware
    base_topic = get_vacuum_mqtt_topic(vacuum_entity_id, hass)
    device_info = get_device_info_from_entity_id(vacuum_entity_id, hass)
    is_rand256 = is_rand256_vacuum(device_info)
    if not is_rand256:
        topic = f"{base_topic}/GoToLocationCapability/go/set"
    else:
        topic = f"{base_topic}/custom_command"

    # Construct payload based on coordinates and firmware
    rand256_payload = (
        {"command": "go_to", "spot_coordinates": {"x": int(x), "y": int(y)}}
        if not spot_id
        else {"command": "go_to", "spot_id": spot_id}
    )
    payload = (
        {"coordinates": {"x": int(x), "y": int(y)}}
        if not is_rand256
        else rand256_payload
    )

    return {
        "entity_id": entity_id,
        "topic": topic,
        "payload": payload,
        "firmware": "Rand256" if is_rand256 else "Valetudo",
    }


def generate_service_data_clean_zone(
    entity_id: str | None,
    device_id: str | None,
    zones: list = None,
    repeat: int = 1,
    after_cleaning: str = "Base",
    hass: HomeAssistant = None,
) -> dict | None:
    """
    Generates the data necessary for sending the service zone clean to the vacuum.
    """
    # Resolve entity ID if only device ID is given
    vacuum_entity_id = get_entity_id(entity_id, device_id, hass)

    # Get the vacuum topic and check firmware
    base_topic = get_vacuum_mqtt_topic(vacuum_entity_id[0], hass)
    device_info = get_device_info_from_entity_id(vacuum_entity_id[0], hass)
    is_rand256 = is_rand256_vacuum(device_info)

    # Check if zones contain strings, indicating zone IDs
    if not is_rand256:
        topic = f"{base_topic}/ZoneCleaningCapability/start/set"
    else:
        topic = f"{base_topic}/custom_command"

    payload = generate_zone_payload(zones, repeat, is_rand256, after_cleaning)

    return {
        "entity_id": entity_id,
        "topic": topic,
        "payload": payload,
        "firmware": "Rand256" if is_rand256 else "Valetudo",
    }


def generate_zone_payload(zones, repeat, is_rand256, after_cleaning="Base"):
    """
    Generates a payload based on the input format for zones and firmware type.
    Args:
        zones (list): The list of coordinates.
        repeat (int): The number of repetitions.
        is_rand256 (bool): Firmware type flag.
        after_cleaning (str): The action to take after cleaning.
    Returns:
        dict: Payload formatted for the specific firmware.
    """
    # Check if zones contain strings, indicating zone IDs
    if is_rand256 and all(isinstance(zone, (str, dict)) for zone in zones):
        # Format payload using zone_ids
        rand256_payload = {
            "command": "zoned_cleanup",
            "zone_ids": [
                {"id": zone, "repeats": repeat} if isinstance(zone, str) else zone
                for zone in zones
            ],
            "afterCleaning": after_cleaning,
        }
        return rand256_payload
    else:
        # Initialize the payload_zones

        payload_zones = []

        # Loop through each zone to determine its format
        for zone in zones:
            _LOGGER.debug(f"Zone: {zone}")
            if len(zone) == 4:
                # Rectangle format with x1, y1, x2, y2
                x1, y1, x2, y2 = zone
                if is_rand256:
                    payload_zones.append(
                        {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "repeats": repeat}
                    )
                else:
                    payload_zones.append(
                        {
                            "points": {
                                "pA": {"x": x1, "y": y1},
                                "pB": {"x": x2, "y": y1},
                                "pC": {"x": x2, "y": y2},
                                "pD": {"x": x1, "y": y2},
                            }
                        }
                    )

            elif len(zone) == 8:
                # Polygon format with x1, y1, x2, y2, x3, y3, x4, y4
                x1, y1, x2, y2, x3, y3, x4, y4 = zone
                if is_rand256:
                    payload_zones.append(
                        {
                            "x1": x1,
                            "y1": y1,
                            "x2": x2,
                            "y2": y2,
                            "x3": x3,
                            "y3": y3,
                            "x4": x4,
                            "y4": y4,
                            "repeats": repeat,
                        }
                    )
                else:
                    payload_zones.append(
                        {
                            "points": {
                                "pA": {"x": x1, "y": y1},
                                "pB": {"x": x2, "y": y2},
                                "pC": {"x": x3, "y": y3},
                                "pD": {"x": x4, "y": y4},
                            }
                        }
                    )
            else:
                raise ValueError(
                    "Invalid zone format. Each zone should contain 4 or 8 coordinates."
                )

        # Return the full payload for the specified firmware
        if is_rand256:
            return {"command": "zoned_cleanup", "zone_coordinates": payload_zones}
        else:
            return {"zones": payload_zones, "iterations": repeat}


def generate_service_data_clean_segments(
    coordinator=None,
    entity_id: str | None = None,
    device_id: str | None = None,
    segments: list = None,
    repeat: int | None = 1,
    after_cleaning: str = "Base",
    hass: HomeAssistant = None,
) -> dict | None:
    """
    Generates the data necessary for sending the service clean segments to the vacuum.
    """
    if not repeat:
        repeat = 1
    # Resolve entity ID if only device ID is given
    vacuum_entity_id = get_entity_id(entity_id, device_id, hass)[0]

    # Get the vacuum topic and check firmware
    have_rooms = coordinator.shared.map_rooms

    base_topic = get_vacuum_mqtt_topic(vacuum_entity_id, hass)
    device_info = get_device_info_from_entity_id(vacuum_entity_id, hass)
    is_rand256 = is_rand256_vacuum(device_info)

    # Check if zones contain strings, indicating zone IDs
    if not is_rand256:
        if isinstance(segments, list):
            segments = [
                str(segment) for segment in segments if not isinstance(segment, list)
            ]
        elif isinstance(segments, str):
            segments = [segments]
        topic = f"{base_topic}/MapSegmentationCapability/clean/set"
        payload = {
            "segment_ids": segments,
            "iterations": int(repeat),
            "customOrder": True,
        }
    else:
        topic = f"{base_topic}/custom_command"
        payload = {
            "command": "segmented_cleanup",
            "segment_ids": (
                convert_string_ids_to_integers(segments)
                if isinstance(segments, list)
                else [segments]
            ),
            "repeats": int(repeat),
            "afterCleaning": after_cleaning,
        }

    return {
        "entity_id": vacuum_entity_id,
        "have_rooms": have_rooms,
        "topic": topic,
        "payload": payload,
        "firmware": "Rand256" if is_rand256 else "Valetudo",
    }


def convert_string_ids_to_integers(ids_list):
    """
    Convert list elements that are strings of numbers to integers.

    Args:
        ids_list (list): List containing potential string or integer IDs.

    Returns:
        list: List with strings converted to integers where applicable.
    """
    converted_list = []
    for item in ids_list:
        try:
            # Attempt to convert to an integer if it's a digit
            converted_list.append(
                int(item) if isinstance(item, str) and item.isdigit() else item
            )
        except ValueError:
            # Log a warning if conversion fails, and keep the original item
            _LOGGER.warning(f"Could not convert item '{item}' to an integer.")
            converted_list.append(item)
    return converted_list

"""
Common functions for the MQTT Vacuum Camera integration.
Version: 2024.12.2
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
    if not vacuum_mqtt_topic or "/" not in vacuum_mqtt_topic:
        raise ValueError("Invalid MQTT topic format")
    # Take the identifier no matter what prefixes are used @markus_sedi.
    return vacuum_mqtt_topic.split("/")[-1].lower() + "_camera"


async def update_options(bk_options, new_options):
    """
    Keep track of the modified options.
    Returns updated options after editing in Config_Flow.
    """

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


def from_device_ids_to_entity_ids(
    device_ids: str, hass: HomeAssistant, domain: str = "vacuum"
) -> str:
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
            # Find all entities linked to this device_id in the domain
            for entry in entity_reg.entities.values():
                if entry.device_id == device_id and entry.domain == domain:
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
    entity_id: str | None,
    device_id: str | None,
    hass: HomeAssistant,
    domain: str = "vacuum",
) -> str | None:
    """Resolve the Entity ID"""
    vacuum_entity_id = entity_id  # Default to entity_id
    if device_id:
        resolved_entities = from_device_ids_to_entity_ids(device_id, hass, domain)
        vacuum_entity_id = resolved_entities
    elif not vacuum_entity_id:
        _LOGGER.error(f"No vacuum entities found for device_id: {device_id}")
        return None
    return vacuum_entity_id


def compose_obstacle_links(vacuum_host_ip: str, obstacles: list) -> list:
    """
    Compose JSON with obstacle details including the image link.
    """
    obstacle_links = []
    if not obstacles or not vacuum_host_ip:
        _LOGGER.debug(
            f"Obstacle links: no obstacles: "
            f"{obstacles} and / or ip: {vacuum_host_ip} to link."
        )
        return None

    for obstacle in obstacles:
        # Extract obstacle details
        label = obstacle.get("label", "")
        points = obstacle.get("points", {})
        image_id = obstacle.get("id", "None")

        if label and points and image_id and vacuum_host_ip:
            # Append formatted obstacle data
            if image_id != "None":
                # Compose the link
                image_link = f"http://{vacuum_host_ip}/api/v2/robot/capabilities/ObstacleImagesCapability/img/{image_id}"
                obstacle_links.append(
                    {
                        "point": points,
                        "label": label,
                        "link": image_link,
                    }
                )
            else:
                obstacle_links.append(
                    {
                        "point": points,
                        "label": label,
                    }
                )

    _LOGGER.debug("Obstacle links: linked data complete.")

    return obstacle_links


class RedactIPFilter(logging.Filter):
    """Remove from the logs IP address"""

    def filter(self, record):
        """Regex to match IP addresses"""
        ip_pattern = r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"
        if record.msg:
            record.msg = re.sub(ip_pattern, "[Redacted IP]", record.msg)
        return True

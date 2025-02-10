"""Collection of services for the vacuums and camera components.
Version 2025.2.0
Autor: @sca075"""

from functools import partial
import logging

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse

# from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from ...common import (
    get_device_info_from_entity_id,
    get_entity_id,
    get_vacuum_mqtt_topic,
    is_rand256_vacuum,
)
from ...const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def validate_zone_or_zone_ids(data):
    """Ensure either zone_list or zone_id is provided."""
    if "zone" not in data and "zone_ids" not in data:
        raise vol.Invalid("Either 'zone' or 'zone_ids' must be provided.")
    return data


SERVICE_SCHEMAS = {
    "vacuum_clean_segments": cv.make_entity_service_schema(
        {
            vol.Required("segments"): cv.ensure_list,
            vol.Required("repeats", default=1): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=3)
            ),
        }
    ),
    "vacuum_clean_zone": cv.make_entity_service_schema(
        {
            vol.Optional("zone"): cv.ensure_list,
            vol.Optional("zone_ids"): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional("repeats", default=1): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=3)
            ),
            vol.Inclusive("zone", "zone_group"): cv.ensure_list,
            vol.Inclusive("zone_ids", "zone_group"): cv.ensure_list,
        },
    ),
    "vacuum_go_to": cv.make_entity_service_schema(
        {
            vol.Optional("spot_id"): cv.string,
            vol.Optional("x_coord"): vol.Coerce(int),
            vol.Optional("y_coord"): vol.Coerce(int),
        }
    ),
    "vacuum_map_save": cv.make_entity_service_schema(
        {
            vol.Required("map_name"): cv.string,
        }
    ),
    "vacuum_map_load": cv.make_entity_service_schema(
        {
            vol.Required("map_name"): cv.string,
        }
    ),
}


async def vacuum_clean_segments(call: ServiceCall, coordinator) -> None:
    """Vacuum Clean Segments (rooms) Action"""
    try:
        # Retrieve coordinates
        segments_lists = call.data.get("segments")
        repeats = call.data.get("repeats")

        # Attempt to get entity_id or device_id
        entity_ids = call.data.get("entity_id")
        device_ids = call.data.get("device_id")

        service_data = generate_service_data_clean_segments(
            coordinator=coordinator,
            entity_id=entity_ids,
            device_id=device_ids,
            segments=segments_lists,
            repeat=repeats,
            hass=coordinator.hass,
        )

        if not service_data:
            _LOGGER.warning("No Service data generated. Aborting!")
            return
        else:
            try:
                await coordinator.connector.publish_to_broker(
                    service_data["topic"],
                    service_data["payload"],
                )
            except Exception as e:
                _LOGGER.warning(f"Error sending command to vacuum: {e}")
                return

            coordinator.hass.bus.async_fire(
                f"event_{DOMAIN}.vacuum_clean_zone",
                {
                    "topic": service_data["topic"],
                    "zones": segments_lists,
                    "repeats": repeats,
                },
                context=call.context,
            )
    except KeyError as e:
        _LOGGER.warning(f"Missing required parameter: {e}")


async def vacuum_clean_zone(call: ServiceCall, coordinator) -> None:
    """Vacuum Zone Clean Action"""

    got_error: str = "No Errors"

    # Retrieve coordinates
    zone_lists = call.data.get("zone", None)
    zone_ids = call.data.get("zone_ids", None)
    repeats = call.data.get("repeats", 1)
    _LOGGER.debug(
        "zone_ids: %s, zone_lists: %s, repeats: %d", zone_ids, zone_lists, repeats
    )
    # Attempt to get entity_id or device_id
    entity_ids = call.data.get("entity_id")
    device_ids = call.data.get("device_id")
    if not zone_lists and not zone_ids:
        got_error = "missing_zone_or_zone_ids"
    elif zone_lists and isinstance(zone_lists, list):
        for sub_zone in zone_lists:
            if len(sub_zone) != 4:
                got_error = "zone_list_length"
    elif zone_lists and (not isinstance(zone_lists, list)):
        got_error = "zone_must_be_list"
    elif zone_ids and isinstance(zone_ids, list):
        zone_lists = zone_ids
    elif not isinstance(zone_ids, list):
        got_error = "zoneid_must_be_list"

    # Raise a ServiceValidationError if there are errors
    if got_error != "No Errors":
        # Raise a ServiceValidationError if there are errors generate WebApi errors.
        _LOGGER.warning(f"Error sending command to vacuum: {got_error}")
        return None

    service_data = generate_service_data_clean_zone(
        entity_id=entity_ids,
        device_id=device_ids,
        zones=zone_lists,
        repeat=repeats,
        hass=coordinator.hass,
    )
    if not service_data:
        _LOGGER.warning("No Service data generated. Aborting!")
        return
    try:
        await coordinator.connector.publish_to_broker(
            service_data["topic"],
            service_data["payload"],
        )
    except Exception as e:
        _LOGGER.warning("Error sending command to vacuum: %s", str(e))
    coordinator.hass.bus.async_fire(
        f"service.{DOMAIN}.vacuum_clean_zone",
        {
            "topic": service_data["topic"],
            "zones": zone_lists,
            "repeats": repeats,
            "result": got_error,
        },
        context=call.context,
    )


async def vacuum_goto(call: ServiceCall, coordinator) -> None:
    """Vacuum Go To Action"""
    try:
        # Retrieve coordinates
        spot_id = call.data.get("spot_id")
        if not spot_id:
            x_coord = call.data["x_coord"]
            y_coord = call.data["y_coord"]
            spot_id = None
        else:
            x_coord = None
            y_coord = None

        # Attempt to get entity_id or device_id
        entity_ids = call.data.get("entity_id")
        device_ids = call.data.get("device_id")

        service_data = generate_service_data_go_to(
            entity_ids, device_ids, x_coord, y_coord, spot_id, coordinator.hass
        )
        if not service_data:
            _LOGGER.warning("No Service data generated. Aborting!")
            return
        try:
            await coordinator.connector.publish_to_broker(
                service_data["topic"],
                service_data["payload"],
            )
        except Exception as e:
            _LOGGER.warning(f"Error sending command to vacuum: {e}")
            return
        coordinator.hass.bus.async_fire(
            f"event_{DOMAIN}.vacuum_go_to",
            {"topic": service_data["topic"], "x": x_coord, "y": y_coord},
            context=call.context,
        )
    except KeyError as e:
        _LOGGER.warning(f"Missing required parameter: {e}")


async def vacuum_map_save(call: ServiceCall, coordinator) -> None:
    """Vacuum Map Save Action"""
    try:
        # Attempt to get entity_id or device_id
        entity_ids = call.data.get("entity_id")
        device_ids = call.data.get("device_id")

        vacuum_entity_id, base_topic, is_a_rand256 = resolve_datas(
            entity_ids, device_ids, coordinator.hass
        )

        map_name = call.data.get("map_name")
        if not map_name:
            _LOGGER.warning("A map name is required to save the map.")
            return
        if is_a_rand256:
            service_data = {
                "topic": f"{base_topic}/custom_command",
                "payload": {
                    "command": "store_map",
                    "name": map_name,
                },
            }
        else:
            _LOGGER.warning("This feature is only available for rand256 vacuums.")
            return
        try:
            await coordinator.connector.publish_to_broker(
                service_data["topic"],
                service_data["payload"],
            )
        except Exception as e:
            _LOGGER.warning(f"Error sending command to vacuum: {e}")
            return

        coordinator.hass.bus.async_fire(
            f"event_{DOMAIN}.vacuum_map_save",
            {"topic": service_data["topic"]},
            context=call.context,
        )
    except KeyError as e:
        _LOGGER.warning(f"Missing required parameter: {e}")


async def vacuum_map_load(call: ServiceCall, coordinator) -> None:
    """Vacuum Map Load Action"""
    try:
        # Attempt to get entity_id or device_id
        entity_ids = call.data.get("entity_id")
        device_ids = call.data.get("device_id")

        vacuum_entity_id, base_topic, is_a_rand256 = resolve_datas(
            entity_ids, device_ids, coordinator.hass
        )

        map_name = call.data.get("map_name")
        if not map_name:
            _LOGGER.warning("A map name is required to load the map.")
            return
        if is_a_rand256:
            service_data = {
                "topic": f"{base_topic}/custom_command",
                "payload": {
                    "command": "load_map",
                    "name": map_name,
                },
            }
        else:
            _LOGGER.warning("This feature is only available for rand256 vacuums.")
            return
        try:
            await coordinator.connector.publish_to_broker(
                service_data["topic"],
                service_data["payload"],
            )
        except Exception as e:
            _LOGGER.warning(f"Error sending command to vacuum: {e}")
            return
        coordinator.hass.bus.async_fire(
            f"event_{DOMAIN}.vacuum_map_load",
            {"topic": service_data["topic"]},
            context=call.context,
        )
        await coordinator.hass.services.async_call(DOMAIN, "reset_trims")
    except KeyError as e:
        _LOGGER.warning(f"Missing required parameter: {e}")


def resolve_datas(
    entity_id: str | None, device_id: str | None, hass: HomeAssistant
) -> tuple:
    """Resolve Vacuum entity_id and base_topic. Determinate also if it is a Rand256 vacuum."""

    # Resolve entity ID if only device ID is given
    vacuum_entity_id = get_entity_id(entity_id, device_id, hass)[0]

    # Get the vacuum topic and check firmware
    base_topic = get_vacuum_mqtt_topic(vacuum_entity_id, hass)
    device_info = get_device_info_from_entity_id(vacuum_entity_id, hass)
    is_rand256 = is_rand256_vacuum(device_info)
    return vacuum_entity_id, base_topic, is_rand256


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
    vacuum_entity_id, base_topic, is_rand256 = resolve_datas(entity_id, device_id, hass)

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
    vacuum_entity_id, base_topic, is_rand256 = resolve_datas(entity_id, device_id, hass)

    # Check if zones contain strings, indicating zone IDs
    if not is_rand256:
        topic = f"{base_topic}/ZoneCleaningCapability/start/set"
    else:
        topic = f"{base_topic}/custom_command"

    payload = generate_zone_payload(zones, repeat, is_rand256, after_cleaning)

    return {
        "entity_id": vacuum_entity_id,
        "topic": topic,
        "payload": payload,
        "firmware": "Rand256" if is_rand256 else "Valetudo",
    }


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
    vacuum_entity_id, base_topic, is_rand256 = resolve_datas(entity_id, device_id, hass)

    # Get the vacuum topic and check firmware
    have_rooms = coordinator.shared.map_rooms

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


SERVICES = {
    "vacuum_go_to": vacuum_goto,
    "vacuum_clean_zone": vacuum_clean_zone,
    "vacuum_clean_segments": vacuum_clean_segments,
    "vacuum_map_save": vacuum_map_save,
    "vacuum_map_load": vacuum_map_load,
}


async def async_register_vacuums_services(hass: HomeAssistant, coordinator) -> None:
    """Register the Vacuums services."""
    for service_name, service_func in SERVICES.items():
        # Use functools.partial to bind the coordinator to the service function
        hass.services.async_register(
            DOMAIN,
            service_name,
            partial(service_func, coordinator=coordinator),
            schema=SERVICE_SCHEMAS.get(service_name),
            supports_response=SupportsResponse.NONE,
        )


async def async_remove_vacuums_services(hass: HomeAssistant) -> None:
    """Remove the Vacuums services."""

    for service_name in SERVICES.keys():
        hass.services.async_remove(DOMAIN, service_name)

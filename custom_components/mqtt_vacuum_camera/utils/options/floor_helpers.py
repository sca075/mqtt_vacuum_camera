"""
Pure helpers for the floor management steps of the options flow.
They take data and return data, without touching the flow handler or Home Assistant.
"""

from typing import Any, Dict, List, Mapping, Tuple

from ...common import create_floor_data
from ...const import (
    CONF_MAP_NAME,
    CONF_TRIM_DOWN,
    CONF_TRIM_LEFT,
    CONF_TRIM_RIGHT,
    CONF_TRIM_UP,
)

DEFAULT_FLOOR_ID = "floor_0"
TRIM_KEYS = ("trim_up", "trim_down", "trim_left", "trim_right")
TRIM_FORM_KEYS = {
    "trim_up": CONF_TRIM_UP,
    "trim_down": CONF_TRIM_DOWN,
    "trim_left": CONF_TRIM_LEFT,
    "trim_right": CONF_TRIM_RIGHT,
}


def floor_dropdown_options(
    ha_floors: List[Dict[str, str]],
    floors_data: Mapping[str, Any],
    filter_configured: bool = False,
    use_configured: bool = False,
) -> List[Dict[str, str]]:
    """Build the {'label', 'value'} options of a floor dropdown.

    Args:
        ha_floors: Home Assistant floors as dicts with 'floor_id' and 'name'.
        floors_data: Floors already configured for the camera.
        filter_configured: Exclude the configured floors (add floor).
        use_configured: Keep only the configured floors (edit / delete floor).
    """
    if not ha_floors:
        return [{"label": "Floor 0", "value": DEFAULT_FLOOR_ID}]

    options = []
    for floor in ha_floors:
        floor_id = floor["floor_id"]
        is_configured = floor_id in floors_data
        if filter_configured and is_configured:
            continue
        if use_configured and not is_configured:
            continue
        options.append({"label": floor["name"], "value": floor_id})
    return options


def trims_from_input(user_input: Mapping[str, Any]) -> Dict[str, int]:
    """Read the four trim values from the form input, 0 when missing."""
    return {key: user_input.get(form_key, 0) for key, form_key in TRIM_FORM_KEYS.items()}


def add_floor(
    floors_data: Mapping[str, Any],
    floor_id: str,
    map_name: str,
    user_input: Mapping[str, Any],
    existing_trims: Mapping[str, Any],
) -> Dict[str, Any]:
    """Return a copy of floors_data with the new floor added.

    The first floor takes the existing auto-calculated trims,
    the next floors take the trims entered in the form.
    """
    if floors_data:
        trims = trims_from_input(user_input)
    else:
        trims = {key: existing_trims.get(key, 0) for key in TRIM_KEYS}

    new_floor = create_floor_data(
        floor_name=floor_id, map_name=map_name, **trims
    )
    return {**floors_data, floor_id: new_floor.to_dict()}


def edit_floor(
    floors_data: Mapping[str, Any],
    floor_id: str,
    user_input: Mapping[str, Any],
) -> Dict[str, Any]:
    """Return a copy of floors_data with the map name and trims of a floor replaced.

    Rotation is not stored here, the library uses the global rotate_image setting.
    """
    updated_floor = create_floor_data(
        floor_name=floor_id,
        map_name=user_input.get(CONF_MAP_NAME, ""),
        rotation=None,
        **trims_from_input(user_input),
    )
    return {**floors_data, floor_id: updated_floor.to_dict()}


def refresh_floor(
    floors_data: Mapping[str, Any],
    floor_id: str,
    current_trims: Mapping[str, Any],
    rotation: int,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Replace the trims and rotation of a floor, keeping its map name.

    Returns:
        The updated floors_data and the trims dict of the updated floor.
    """
    map_name = floors_data.get(floor_id, {}).get("map_name", "")
    trims = {key: current_trims.get(key, 0) for key in TRIM_KEYS}
    updated_floor = create_floor_data(
        floor_name=floor_id, map_name=map_name, rotation=rotation, **trims
    )
    return (
        {**floors_data, floor_id: updated_floor.to_dict()},
        updated_floor.trims.to_dict(),
    )


def delete_floor(
    floors_data: Mapping[str, Any],
    floor_id: str,
    current_floor: str,
    ha_floors: List[Dict[str, str]],
) -> Tuple[Dict[str, Any], str]:
    """Return floors_data without the floor and the floor that must be current.

    When the current floor is deleted the first remaining floor is used,
    then the first Home Assistant floor, then floor_0.
    """
    remaining = {key: value for key, value in floors_data.items() if key != floor_id}
    if floor_id != current_floor:
        return remaining, current_floor
    if remaining:
        return remaining, next(iter(remaining))
    if ha_floors:
        return remaining, ha_floors[0]["floor_id"]
    return remaining, DEFAULT_FLOOR_ID


def add_floor_description(has_floors: bool) -> str:
    """Return the description shown in the add floor form."""
    if has_floors:
        return (
            "Add a new floor. Enter trim values or leave at 0 to auto-calculate "
            "when you use 'Save Map Trims'."
        )
    return (
        "Add a new floor. "
        "Existing auto-calculated trim values will be used for this first floor."
    )


def trim_info(floor_data: Mapping[str, Any]) -> str:
    """Return the current trims of a floor as text for the edit floor form."""
    trims = floor_data.get("trims", {})
    return (
        f"Current trims: {trims.get('trim_up', 0)}, "
        f"{trims.get('trim_left', 0)}, "
        f"{trims.get('trim_down', 0)}, "
        f"{trims.get('trim_right', 0)}"
    )

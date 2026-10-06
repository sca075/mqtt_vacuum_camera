"""Unit tests for the options flow helpers (option_fields and floor_helpers)."""

from custom_components.mqtt_vacuum_camera.const import (
    ATTR_ROTATE,
    COLOR_WALL,
    CONF_TRIM_DOWN,
    CONF_TRIM_LEFT,
    CONF_TRIM_RIGHT,
    CONF_TRIM_UP,
)
from custom_components.mqtt_vacuum_camera.utils.options import floor_helpers
from custom_components.mqtt_vacuum_camera.utils.options.option_fields import (
    BASE_COLOURS_FIELDS,
    IMAGE_BASIC_FIELDS,
    extract_options,
    room_fields,
    same_key_fields,
)

HA_FLOORS = [
    {"floor_id": "ground", "name": "Ground"},
    {"floor_id": "first", "name": "First"},
]


def floor(name, up=0, down=0, left=0, right=0, map_name=""):
    """Expected floors_data entry without rotation."""
    return {
        "trims": {
            "floor": name,
            "trim_up": up,
            "trim_left": left,
            "trim_down": down,
            "trim_right": right,
        },
        "map_name": map_name,
    }


# option_fields


def test_extract_options_maps_form_keys_to_option_keys():
    result = extract_options({COLOR_WALL: [1, 2, 3]}, {"color_wall": COLOR_WALL})
    assert result == {"color_wall": [1, 2, 3]}


def test_extract_options_missing_keys_are_none():
    result = extract_options({}, IMAGE_BASIC_FIELDS)
    assert set(result) == set(IMAGE_BASIC_FIELDS)
    assert all(value is None for value in result.values())


def test_extract_options_uses_default_for_missing_keys():
    assert extract_options({"a": True}, same_key_fields(["a", "b"]), default=False) == {
        "a": True,
        "b": False,
    }


def test_extract_options_ignores_unknown_input_keys():
    assert extract_options({"other": 1}, {"color_wall": COLOR_WALL}) == {
        "color_wall": None
    }


def test_room_fields_builds_room_range():
    assert room_fields("color_room", 8, 10) == {
        "color_room_8": "color_room_8",
        "color_room_9": "color_room_9",
    }
    assert room_fields("color_room", 8, 8) == {}


def test_field_maps_keep_stored_key_names():
    assert BASE_COLOURS_FIELDS["color_wall"] == COLOR_WALL
    assert IMAGE_BASIC_FIELDS["rotate_image"] == ATTR_ROTATE


# floor_dropdown_options


def test_dropdown_without_ha_floors_returns_floor_0():
    assert floor_helpers.floor_dropdown_options([], {}) == [
        {"label": "Floor 0", "value": "floor_0"}
    ]


def test_dropdown_lists_all_ha_floors():
    assert floor_helpers.floor_dropdown_options(HA_FLOORS, {"ground": {}}) == [
        {"label": "Ground", "value": "ground"},
        {"label": "First", "value": "first"},
    ]


def test_dropdown_filter_configured_excludes_configured():
    result = floor_helpers.floor_dropdown_options(
        HA_FLOORS, {"ground": {}}, filter_configured=True
    )
    assert result == [{"label": "First", "value": "first"}]


def test_dropdown_use_configured_keeps_only_configured():
    result = floor_helpers.floor_dropdown_options(
        HA_FLOORS, {"ground": {}}, use_configured=True
    )
    assert result == [{"label": "Ground", "value": "ground"}]


# add / edit / refresh / delete


def test_trims_from_input_defaults_to_zero():
    assert floor_helpers.trims_from_input({CONF_TRIM_UP: 5}) == {
        "trim_up": 5,
        "trim_down": 0,
        "trim_left": 0,
        "trim_right": 0,
    }


def test_add_first_floor_uses_existing_trims():
    result = floor_helpers.add_floor(
        {},
        "floor_0",
        "Ground",
        {CONF_TRIM_UP: 99},
        {"trim_up": 1, "trim_down": 2, "trim_left": 3, "trim_right": 4},
    )
    assert result["floor_0"]["trims"]["trim_up"] == 1
    assert result["floor_0"]["trims"]["trim_right"] == 4
    assert result["floor_0"]["map_name"] == "Ground"


def test_add_next_floor_uses_form_trims_and_keeps_existing_floors():
    existing = {"floor_0": floor("floor_0")}
    result = floor_helpers.add_floor(
        existing,
        "floor_1",
        "Up",
        {
            CONF_TRIM_UP: 1,
            CONF_TRIM_DOWN: 2,
            CONF_TRIM_LEFT: 3,
            CONF_TRIM_RIGHT: 4,
        },
        {"trim_up": 50},
    )
    assert result["floor_0"] == existing["floor_0"]
    assert result["floor_1"]["trims"] == {
        "floor": "floor_1",
        "trim_up": 1,
        "trim_down": 2,
        "trim_left": 3,
        "trim_right": 4,
    }
    assert result["floor_1"]["map_name"] == "Up"
    assert list(existing) == ["floor_0"]


def test_edit_floor_replaces_map_name_and_trims_without_rotation():
    existing = {"floor_0": floor("floor_0", map_name="Old")}
    result = floor_helpers.edit_floor(
        existing, "floor_0", {"map_name": "New", CONF_TRIM_LEFT: 7}
    )
    # FloorData defaults the rotation to 0 when none is given
    expected = {**floor("floor_0", left=7, map_name="New"), "rotation": 0}
    assert result == {"floor_0": expected}
    assert existing["floor_0"]["map_name"] == "Old"


def test_refresh_floor_keeps_map_name_and_sets_rotation():
    existing = {"floor_0": floor("floor_0", map_name="Home")}
    floors, trims = floor_helpers.refresh_floor(
        existing, "floor_0", {"trim_up": 1, "trim_left": 2}, 90
    )
    assert floors["floor_0"]["map_name"] == "Home"
    assert floors["floor_0"]["rotation"] == 90
    assert trims == {
        "floor": "floor_0",
        "trim_up": 1,
        "trim_left": 2,
        "trim_down": 0,
        "trim_right": 0,
    }
    assert "rotation" not in existing["floor_0"]


def test_delete_floor_keeps_current_when_other_floor_deleted():
    floors = {"a": {}, "b": {}}
    assert floor_helpers.delete_floor(floors, "b", "a", []) == ({"a": {}}, "a")
    assert floors == {"a": {}, "b": {}}


def test_delete_current_floor_selects_first_remaining():
    assert floor_helpers.delete_floor({"a": {}, "b": {}}, "a", "a", HA_FLOORS) == (
        {"b": {}},
        "b",
    )


def test_delete_last_floor_falls_back_to_ha_floor_then_floor_0():
    assert floor_helpers.delete_floor({"a": {}}, "a", "a", HA_FLOORS) == ({}, "ground")
    assert floor_helpers.delete_floor({"a": {}}, "a", "a", []) == ({}, "floor_0")


# texts


def test_add_floor_description_depends_on_existing_floors():
    assert "first floor" in floor_helpers.add_floor_description(False)
    assert "Save Map Trims" in floor_helpers.add_floor_description(True)


def test_trim_info_orders_up_left_down_right():
    info = floor_helpers.trim_info(floor("f", up=1, left=2, down=3, right=4))
    assert info == "Current trims: 1, 2, 3, 4"
    assert floor_helpers.trim_info({}) == "Current trims: 0, 0, 0, 0"

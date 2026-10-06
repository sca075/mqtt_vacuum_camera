"""Characterization tests for the options flow handler.

They pin the current behaviour of MQTTCameraOptionsFlowHandler (keys written to
camera_options, next step reached, floor bookkeeping) so the flow can be
refactored without changing what the user gets.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from custom_components.mqtt_vacuum_camera.const import (
    ALPHA_BACKGROUND,
    ALPHA_CARPET,
    ALPHA_CHARGER,
    ALPHA_GO_TO,
    ALPHA_MATERIAL_TILE,
    ALPHA_MATERIAL_WOOD,
    ALPHA_MOP_MOVE,
    ALPHA_MOVE,
    ALPHA_NO_GO,
    ALPHA_ROBOT,
    ALPHA_ROOM_0,
    ALPHA_TEXT,
    ALPHA_WALL,
    ALPHA_ZONE_CLEAN,
    ATTR_MARGINS,
    ATTR_ROTATE,
    COLOR_BACKGROUND,
    COLOR_CARPET,
    COLOR_CHARGER,
    COLOR_GO_TO,
    COLOR_MATERIAL_TILE,
    COLOR_MATERIAL_WOOD,
    COLOR_MOP_MOVE,
    COLOR_MOVE,
    COLOR_NO_GO,
    COLOR_ROBOT,
    COLOR_ROOM_0,
    COLOR_TEXT,
    COLOR_WALL,
    COLOR_ZONE_CLEAN,
    CONF_ASPECT_RATIO,
    CONF_AUTO_ZOOM,
    CONF_CURRENT_FLOOR,
    CONF_DEF_CONTEXT_TYPE,
    CONF_DISABLE_CARPETS,
    CONF_DISABLE_MATERIAL_OVERLAY,
    CONF_FLOOR_NAME,
    CONF_FLOORS_DATA,
    CONF_MAP_NAME,
    CONF_MOP_PATH_WIDTH,
    CONF_OBSTACLE_LINK_IP,
    CONF_OBSTACLE_LINK_PORT,
    CONF_OBSTACLE_LINK_PROTOCOL,
    CONF_ROBOT_SIZE,
    CONF_TRIM_DOWN,
    CONF_TRIM_LEFT,
    CONF_TRIM_RIGHT,
    CONF_TRIM_UP,
    CONF_VAC_STAT,
    CONF_VAC_STAT_FONT,
    CONF_VAC_STAT_POS,
    CONF_VAC_STAT_SIZE,
    CONF_ZOOM_LOCK_RATIO,
    DEFAULT_ROOMS_NAMES,
    DOMAIN,
    DRAW_FLAGS,
    IS_ALPHA,
    IS_ALPHA_R1,
    IS_ALPHA_R2,
    ROOM_FLAGS,
)
from custom_components.mqtt_vacuum_camera.options_flow import (
    MQTTCameraOptionsFlowHandler,
)

MODULE = "custom_components.mqtt_vacuum_camera.options_flow"


def make_floor(floor_id: str, map_name: str = "", trim_up: int = 0) -> dict:
    """Build a floors_data entry in the stored format."""
    return {
        "trims": {
            "floor": floor_id,
            "trim_up": trim_up,
            "trim_left": 0,
            "trim_down": 0,
            "trim_right": 0,
        },
        "map_name": map_name,
    }


@pytest.fixture
def config_entry():
    """Config entry with no floors configured."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "entry_1"
    entry.unique_id = "Vacuum_One_camera"
    entry.options = {}
    return entry


@pytest.fixture
def make_flow(config_entry):
    """Factory returning a flow handler for the given entry options."""

    def _make(options=None, rooms=3):
        """Create a flow handler with the given entry options and room count."""
        config_entry.options = options or {}
        flow = MQTTCameraOptionsFlowHandler(config_entry)
        flow.hass = MagicMock()
        flow.number_of_rooms = rooms
        return flow

    return _make


@pytest.fixture
def flow(make_flow):
    """Flow handler with 3 rooms and no floors."""
    return make_flow()


def assert_step(result, step_id, result_type=FlowResultType.FORM):
    """Assert a flow result is the given type and step."""
    assert result["type"] == result_type
    assert result["step_id"] == step_id


# --- initialisation -------------------------------------------------------


def test_init_requires_config_entry():
    """The handler refuses to start without a config entry."""
    with pytest.raises(ConfigEntryError):
        MQTTCameraOptionsFlowHandler(None)


def test_init_defaults(flow, config_entry):
    """A new handler starts with empty options, no floors and floor_0 selected."""
    assert flow.file_name == "vacuum_one"
    assert flow.camera_options == {}
    assert flow.floors_data == {}
    assert flow.current_floor == "floor_0"
    assert flow.selected_floor is None
    assert flow.is_alpha_enabled is False


def test_init_reads_floors_from_options(make_flow):
    """Floors and the current floor are read from the entry options."""
    options = {"floors_data": {"floor_1": make_floor("floor_1")}, "current_floor": "floor_1"}
    flow = make_flow(options)
    assert flow.floors_data == options["floors_data"]
    assert flow.current_floor == "floor_1"


def test_init_backup_options_is_deep_copy(make_flow):
    """Later changes to the entry options do not alter the backup."""
    options = {"floors_data": {"floor_1": make_floor("floor_1")}}
    flow = make_flow(options)
    options["floors_data"]["floor_1"]["map_name"] = "changed"
    assert flow.backup_options["floors_data"]["floor_1"]["map_name"] == ""


# --- menus ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("step", "expected"),
    [
        (
            "image_opt",
            [
                "image_basic_opt",
                "status_text",
                "draw_elements",
                "floor_management",
                "obstacle_link_config",
                "main_menu",
            ],
        ),
        ("draw_elements", ["map_elements", "segments_visibility", "main_menu"]),
        (
            "floor_management",
            [
                "select_floor",
                "add_floor",
                "edit_floor",
                "delete_floor",
                "update_floor_data",
                "main_menu",
            ],
        ),
    ],
)
async def test_static_menus(flow, step, expected):
    """Static menus list their expected options in order."""
    result = await getattr(flow, f"async_step_{step}")()
    assert_step(result, step, FlowResultType.MENU)
    assert result["menu_options"] == expected


@pytest.mark.parametrize(
    ("rooms", "alpha", "expected"),
    [
        (1, False, ["base_colours", "floor_only", "main_menu"]),
        (5, False, ["base_colours", "rooms_colours_1", "main_menu"]),
        (8, False, ["base_colours", "rooms_colours_1", "main_menu"]),
        (12, False, ["base_colours", "rooms_colours_1", "rooms_colours_2", "main_menu"]),
        (5, True, ["base_colours", "rooms_colours_1", "transparency", "main_menu"]),
    ],
)
async def test_colours_menu(make_flow, rooms, alpha, expected):
    """The colours menu depends on the room count and the alpha flag."""
    flow = make_flow(rooms=rooms)
    flow.is_alpha_enabled = alpha
    result = await flow.async_step_colours()
    assert result["menu_options"] == expected


@pytest.mark.parametrize(
    ("rooms", "expected"),
    [
        (1, ["alpha_1", "alpha_floor", "main_menu"]),
        (8, ["alpha_1", "alpha_2", "main_menu"]),
        (12, ["alpha_1", "alpha_2", "alpha_3", "main_menu"]),
    ],
)
async def test_transparency_menu(make_flow, rooms, expected):
    """The transparency menu depends on the room count."""
    result = await make_flow(rooms=rooms).async_step_transparency()
    assert result["menu_options"] == expected


async def test_init_menu_reads_room_store(flow):
    """The init step reads the room count and names from the RoomStore."""
    with patch(f"{MODULE}.RoomStore") as room_store:
        room_store.return_value.get_rooms_count.return_value = 4
        room_store.return_value.room_names = {"room_0": "Kitchen"}
        result = await flow.async_step_init()
    room_store.assert_called_once_with("vacuum_one")
    assert_step(result, "init", FlowResultType.MENU)
    assert result["menu_options"] == ["image_opt", "colours", "materials", "save_options"]
    assert flow.number_of_rooms == 4
    assert flow.rooms_placeholders == {"room_0": "Kitchen"}


async def test_init_menu_default_room_names(flow):
    """The init step uses the default room names when the store has none."""
    with patch(f"{MODULE}.RoomStore") as room_store:
        room_store.return_value.get_rooms_count.return_value = 2
        room_store.return_value.room_names = None
        await flow.async_step_init()
    assert flow.rooms_placeholders == DEFAULT_ROOMS_NAMES


@pytest.mark.parametrize("rooms", [0, None, "3"])
async def test_init_aborts_without_rooms(flow, rooms):
    """The init step aborts when the room count is missing or invalid."""
    with patch(f"{MODULE}.RoomStore") as room_store:
        room_store.return_value.get_rooms_count.return_value = rooms
        room_store.return_value.room_names = None
        result = await flow.async_step_init()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_rooms"


async def test_main_menu_goes_to_init(flow):
    """The main menu step returns to the init step."""
    flow.async_step_init = AsyncMock(return_value="init_result")
    assert await flow.async_step_main_menu() == "init_result"


# --- simple form steps: keys written and next step ------------------------


FORM_STEPS = [
    pytest.param(
        "materials",
        {
            CONF_DISABLE_MATERIAL_OVERLAY: True,
            CONF_DISABLE_CARPETS: False,
            COLOR_CARPET: [1, 2, 3],
            COLOR_MATERIAL_WOOD: [4, 5, 6],
            COLOR_MATERIAL_TILE: [7, 8, 9],
            ALPHA_CARPET: 10,
            ALPHA_MATERIAL_WOOD: 20,
            ALPHA_MATERIAL_TILE: 30,
        },
        {
            "disable_material_overlay": True,
            "disable_carpets": False,
            "color_carpet": [1, 2, 3],
            "color_material_wood": [4, 5, 6],
            "color_material_tile": [7, 8, 9],
            "alpha_carpet": 10,
            "alpha_material_wood": 20,
            "alpha_material_tile": 30,
        },
        "init",
        id="materials",
    ),
    pytest.param(
        "image_basic_opt",
        {
            ATTR_ROTATE: "90",
            ATTR_MARGINS: "5",
            CONF_ASPECT_RATIO: "16, 9",
            CONF_ZOOM_LOCK_RATIO: True,
            CONF_AUTO_ZOOM: False,
            CONF_ROBOT_SIZE: 25,
            CONF_MOP_PATH_WIDTH: 7,
            CONF_DEF_CONTEXT_TYPE: "default",
        },
        {
            "rotate_image": "90",
            "margins": "5",
            "aspect_ratio": "16, 9",
            "zoom_lock_ratio": True,
            "auto_zoom": False,
            "robot_size": 25,
            "mop_path_width": 7,
            "def_context_type": "default",
        },
        "image_opt",
        id="image_basic_opt",
    ),
    pytest.param(
        "status_text",
        {
            CONF_VAC_STAT: True,
            CONF_VAC_STAT_FONT: "Arial",
            CONF_VAC_STAT_SIZE: 50,
            CONF_VAC_STAT_POS: True,
            COLOR_TEXT: [1, 1, 1],
        },
        {
            "show_vac_status": True,
            "vac_status_font": "Arial",
            "vac_status_size": 50,
            "vac_status_position": True,
            "color_text": [1, 1, 1],
        },
        "image_opt",
        id="status_text",
    ),
    pytest.param(
        "obstacle_link_config",
        {
            CONF_OBSTACLE_LINK_PROTOCOL: "http",
            CONF_OBSTACLE_LINK_PORT: 8080,
            CONF_OBSTACLE_LINK_IP: "10.0.0.2",
        },
        {
            CONF_OBSTACLE_LINK_PROTOCOL: "http",
            CONF_OBSTACLE_LINK_PORT: 8080,
            CONF_OBSTACLE_LINK_IP: "10.0.0.2",
        },
        "image_opt",
        id="obstacle_link_config",
    ),
    pytest.param(
        "alpha_1",
        {
            ALPHA_CHARGER: 1,
            ALPHA_MOVE: 2,
            ALPHA_MOP_MOVE: 3,
            ALPHA_WALL: 4,
            ALPHA_ROBOT: 5,
            ALPHA_GO_TO: 6,
            ALPHA_NO_GO: 7,
            ALPHA_ZONE_CLEAN: 8,
            ALPHA_BACKGROUND: 9,
            ALPHA_TEXT: 10,
        },
        {
            "alpha_charger": 1,
            "alpha_move": 2,
            "alpha_mop_move": 3,
            "alpha_wall": 4,
            "alpha_robot": 5,
            "alpha_go_to": 6,
            "alpha_no_go": 7,
            "alpha_zone_clean": 8,
            "alpha_background": 9,
            "alpha_text": 10,
        },
        "transparency",
        id="alpha_1",
    ),
    pytest.param(
        "alpha_floor",
        {ALPHA_ROOM_0: 55},
        {"alpha_room_0": 55},
        "transparency",
        id="alpha_floor",
    ),
]


@pytest.mark.parametrize(("step", "user_input", "expected", "next_step"), FORM_STEPS)
async def test_form_step_stores_options(flow, step, user_input, expected, next_step):
    """A submitted form step stores its options and moves to the next step."""
    result = await getattr(flow, f"async_step_{step}")(user_input)
    assert flow.camera_options == expected
    assert result["step_id"] == next_step


@pytest.mark.parametrize(("step", "user_input", "expected", "next_step"), FORM_STEPS)
async def test_form_step_missing_keys_store_none(flow, step, user_input, expected, next_step):
    """An empty submission still writes every key, with value None."""
    await getattr(flow, f"async_step_{step}")({})
    assert flow.camera_options == dict.fromkeys(expected)


@pytest.mark.parametrize("step", [p.values[0] for p in FORM_STEPS])
async def test_form_step_without_input_shows_form(flow, step):
    """A form step without input shows its form and stores nothing."""
    flow.hass.data = {}
    result = await getattr(flow, f"async_step_{step}")()
    assert_step(result, step)
    assert flow.camera_options == {}


async def test_obstacle_link_form_uses_coordinator_ip(flow, config_entry):
    """The obstacle link form defaults to the vacuum IP of the coordinator."""
    coordinator = MagicMock()
    coordinator.context.shared.vacuum_ips = "192.168.1.9"
    flow.hass.data = {DOMAIN: {config_entry.entry_id: {"coordinator": coordinator}}}
    flow._schemas = MagicMock()
    await flow.async_step_obstacle_link_config()
    flow._schemas.obstacle_link_schema.assert_called_once_with("192.168.1.9")


async def test_obstacle_link_form_defaults_to_empty_ip(flow):
    """The obstacle link form defaults to an empty IP without a coordinator."""
    flow.hass.data = {}
    flow._schemas = MagicMock()
    await flow.async_step_obstacle_link_config()
    flow._schemas.obstacle_link_schema.assert_called_once_with("")


# --- draw elements --------------------------------------------------------


async def test_map_elements_stores_all_draw_flags(flow):
    """Map elements stores every draw flag, False when not submitted."""
    result = await flow.async_step_map_elements({DRAW_FLAGS[0]: True})
    assert set(flow.camera_options) == set(DRAW_FLAGS)
    assert flow.camera_options[DRAW_FLAGS[0]] is True
    assert all(flow.camera_options[f] is False for f in DRAW_FLAGS[1:])
    assert result["step_id"] == "draw_elements"


@pytest.mark.parametrize(("rooms", "stored"), [(3, 3), (15, 15), (20, 15)])
async def test_segments_visibility_limits_room_flags(make_flow, rooms, stored):
    """Segments visibility stores room flags only up to the room count (max 15)."""
    flow = make_flow(rooms=rooms)
    result = await flow.async_step_segments_visibility({ROOM_FLAGS[0]: True})
    assert list(flow.camera_options) == ROOM_FLAGS[:stored]
    assert flow.camera_options[ROOM_FLAGS[0]] is True
    assert result["step_id"] == "draw_elements"


async def test_segments_visibility_form(flow):
    """The segments visibility form receives the room placeholders."""
    result = await flow.async_step_segments_visibility()
    assert_step(result, "segments_visibility")
    assert result["description_placeholders"] == flow.rooms_placeholders


# --- colours --------------------------------------------------------------

BASE_COLOURS_INPUT = {
    COLOR_CHARGER: [1, 0, 0],
    COLOR_MOVE: [2, 0, 0],
    COLOR_MOP_MOVE: [3, 0, 0],
    COLOR_WALL: [4, 0, 0],
    COLOR_ROBOT: [5, 0, 0],
    COLOR_GO_TO: [6, 0, 0],
    COLOR_NO_GO: [7, 0, 0],
    COLOR_ZONE_CLEAN: [8, 0, 0],
    COLOR_BACKGROUND: [9, 0, 0],
}
BASE_COLOURS_EXPECTED = {
    "color_charger": [1, 0, 0],
    "color_move": [2, 0, 0],
    "color_mop_move": [3, 0, 0],
    "color_wall": [4, 0, 0],
    "color_robot": [5, 0, 0],
    "color_go_to": [6, 0, 0],
    "color_no_go": [7, 0, 0],
    "color_zone_clean": [8, 0, 0],
    "color_background": [9, 0, 0],
}


async def test_base_colours_without_alpha(flow):
    """Base colours are stored and the flow returns to the colours menu."""
    result = await flow.async_step_base_colours(BASE_COLOURS_INPUT)
    assert flow.camera_options == BASE_COLOURS_EXPECTED
    assert flow.is_alpha_enabled is False
    assert result["step_id"] == "colours"


async def test_base_colours_with_alpha_goes_to_alpha_1(flow):
    """Base colours with the alpha flag continue to alpha_1 and reset the flag."""
    result = await flow.async_step_base_colours({**BASE_COLOURS_INPUT, IS_ALPHA: True})
    assert flow.camera_options == BASE_COLOURS_EXPECTED
    # The flag is reset right away so the colours menu hides "transparency".
    assert flow.is_alpha_enabled is False
    assert_step(result, "alpha_1")


async def test_base_colours_form(flow):
    """The base colours form is shown without input."""
    assert_step(await flow.async_step_base_colours(), "base_colours")


async def test_floor_only(flow):
    """Floor only stores the room 0 colour and returns to the colours menu."""
    result = await flow.async_step_floor_only({COLOR_ROOM_0: [1, 2, 3]})
    assert flow.camera_options == {"color_room_0": [1, 2, 3]}
    assert flow.is_alpha_enabled is False
    assert result["step_id"] == "colours"


async def test_floor_only_with_alpha(flow):
    """Floor only with the alpha flag continues to the floor transparency step."""
    result = await flow.async_step_floor_only({COLOR_ROOM_0: [1, 2, 3], IS_ALPHA_R1: True})
    assert flow.is_alpha_enabled is True
    assert_step(result, "alpha_floor")


async def test_floor_only_form(flow):
    """The floor only form is shown without input."""
    assert_step(await flow.async_step_floor_only(), "floor_only")


@pytest.mark.parametrize(("rooms", "stored"), [(1, 1), (5, 5), (8, 8), (12, 8)])
async def test_rooms_colours_1_stores_first_rooms(make_flow, rooms, stored):
    """Rooms colours 1 stores at most the first 8 room colours."""
    flow = make_flow(rooms=rooms)
    user_input = {f"color_room_{i}": [i, i, i] for i in range(16)}
    result = await flow.async_step_rooms_colours_1(user_input)
    assert flow.camera_options == {f"color_room_{i}": [i, i, i] for i in range(stored)}
    assert result["step_id"] == "colours"


async def test_rooms_colours_1_missing_key_is_none(make_flow):
    """Rooms colours 1 stores None for the room colours not submitted."""
    flow = make_flow(rooms=2)
    await flow.async_step_rooms_colours_1({"color_room_0": [1, 1, 1]})
    assert flow.camera_options == {"color_room_0": [1, 1, 1], "color_room_1": None}


async def test_rooms_colours_1_with_alpha(flow):
    """Rooms colours 1 with the alpha flag continues to alpha_2."""
    result = await flow.async_step_rooms_colours_1({IS_ALPHA_R1: True})
    assert flow.is_alpha_enabled is True
    assert_step(result, "alpha_2")


@pytest.mark.parametrize(("rooms", "last"), [(10, 10), (16, 16), (20, 16)])
async def test_rooms_colours_2_stores_rooms_8_and_up(make_flow, rooms, last):
    """Rooms colours 2 stores the room colours from room 8 up to 16 at most."""
    flow = make_flow(rooms=rooms)
    user_input = {f"color_room_{i}": [i, i, i] for i in range(20)}
    result = await flow.async_step_rooms_colours_2(user_input)
    assert flow.camera_options == {f"color_room_{i}": [i, i, i] for i in range(8, last)}
    assert result["step_id"] == "colours"


async def test_rooms_colours_2_with_alpha(make_flow):
    """Rooms colours 2 with the alpha flag continues to alpha_3."""
    flow = make_flow(rooms=12)
    result = await flow.async_step_rooms_colours_2({IS_ALPHA_R2: True})
    assert flow.is_alpha_enabled is True
    assert_step(result, "alpha_3")


@pytest.mark.parametrize("step", ["rooms_colours_1", "rooms_colours_2", "alpha_2", "alpha_3"])
async def test_room_forms_are_shown(make_flow, step):
    """Room colour and alpha forms are shown with the room placeholders."""
    flow = make_flow(rooms=12)
    result = await getattr(flow, f"async_step_{step}")()
    assert_step(result, step)
    assert result["description_placeholders"] == flow.rooms_placeholders


@pytest.mark.parametrize(("rooms", "stored"), [(1, 1), (5, 5), (12, 8)])
async def test_alpha_2_stores_first_rooms(make_flow, rooms, stored):
    """Alpha 2 stores at most the first 8 room transparencies."""
    flow = make_flow(rooms=rooms)
    user_input = {f"alpha_room_{i}": i for i in range(16)}
    result = await flow.async_step_alpha_2(user_input)
    assert flow.camera_options == {f"alpha_room_{i}": i for i in range(stored)}
    assert result["step_id"] == "transparency"


@pytest.mark.parametrize(("rooms", "last"), [(10, 10), (20, 16)])
async def test_alpha_3_stores_rooms_8_and_up(make_flow, rooms, last):
    """Alpha 3 stores the room transparencies from room 8 up to 16 at most."""
    flow = make_flow(rooms=rooms)
    user_input = {f"alpha_room_{i}": i for i in range(20)}
    result = await flow.async_step_alpha_3(user_input)
    assert flow.camera_options == {f"alpha_room_{i}": i for i in range(8, last)}
    assert result["step_id"] == "transparency"


# --- floor helpers --------------------------------------------------------


def test_get_ha_floors(flow):
    """The Home Assistant floors are returned with their id and name."""
    floor = MagicMock()
    floor.floor_id = "ground"
    floor.name = "Ground"
    with patch(f"{MODULE}.fr.async_get") as async_get:
        async_get.return_value.async_list_floors.return_value = [floor]
        assert flow._get_ha_floors() == [{"floor_id": "ground", "name": "Ground"}]


def test_get_ha_floors_empty(flow):
    """No Home Assistant floors gives an empty list."""
    with patch(f"{MODULE}.fr.async_get") as async_get:
        async_get.return_value.async_list_floors.return_value = []
        assert flow._get_ha_floors() == []


@pytest.mark.parametrize("error", [AttributeError, ValueError, KeyError])
def test_get_ha_floors_error_returns_empty(flow, error):
    """A floor registry error gives an empty list."""
    with patch(f"{MODULE}.fr.async_get", side_effect=error("boom")):
        assert flow._get_ha_floors() == []


def test_dropdown_without_ha_floors(flow):
    """Without Home Assistant floors the dropdown offers floor_0 only."""
    with patch.object(flow, "_get_ha_floors", return_value=[]):
        expected = [{"label": "Floor 0", "value": "floor_0"}]
        assert flow._get_floor_dropdown_options() == expected
        assert flow._get_floor_dropdown_options(filter_configured=True) == expected
        assert flow._get_floor_dropdown_options(use_configured=True) == expected


HA_FLOORS = [
    {"floor_id": "a", "name": "A"},
    {"floor_id": "b", "name": "B"},
    {"floor_id": "c", "name": "C"},
]


def test_dropdown_options_filters(make_flow):
    """The dropdown can exclude or keep only the configured floors."""
    flow = make_flow({"floors_data": {"b": make_floor("b")}})
    with patch.object(flow, "_get_ha_floors", return_value=HA_FLOORS):
        assert [o["value"] for o in flow._get_floor_dropdown_options()] == ["a", "b", "c"]
        assert [
            o["value"] for o in flow._get_floor_dropdown_options(filter_configured=True)
        ] == ["a", "c"]
        assert [
            o["value"] for o in flow._get_floor_dropdown_options(use_configured=True)
        ] == ["b"]
        assert flow._get_floor_dropdown_options(use_configured=True) == [
            {"label": "B", "value": "b"}
        ]


# --- floor management -----------------------------------------------------


async def test_select_floor(flow):
    """Selecting a floor updates the current floor and the camera options."""
    result = await flow.async_step_select_floor({CONF_CURRENT_FLOOR: "floor_2"})
    assert flow.current_floor == "floor_2"
    assert flow.camera_options == {CONF_CURRENT_FLOOR: "floor_2"}
    assert result["step_id"] == "floor_management"


async def test_select_floor_form(flow):
    """The select floor form shows the current floor."""
    with patch.object(flow, "_get_ha_floors", return_value=[]):
        result = await flow.async_step_select_floor()
    assert_step(result, "select_floor")
    assert result["description_placeholders"] == {"current_floor": "floor_0"}


async def test_add_first_floor_uses_existing_trims_data(make_flow):
    """The first floor takes the existing trims_data, not the form trims."""
    flow = make_flow(
        {
            "trims_data": {
                "trim_up": 1,
                "trim_down": 2,
                "trim_left": 3,
                "trim_right": 4,
            }
        }
    )
    result = await flow.async_step_add_floor(
        {
            CONF_FLOOR_NAME: "floor_0",
            CONF_MAP_NAME: "Ground",
            CONF_TRIM_UP: 99,
            CONF_TRIM_DOWN: 99,
            CONF_TRIM_LEFT: 99,
            CONF_TRIM_RIGHT: 99,
        }
    )
    expected = {
        "floor_0": {
            "trims": {
                "floor": "floor_0",
                "trim_up": 1,
                "trim_left": 3,
                "trim_down": 2,
                "trim_right": 4,
            },
            "map_name": "Ground",
            "rotation": 0,
        }
    }
    assert flow.floors_data == expected
    assert flow.current_floor == "floor_0"
    assert flow.camera_options == {
        CONF_FLOORS_DATA: expected,
        CONF_CURRENT_FLOOR: "floor_0",
    }
    assert result["step_id"] == "floor_management"


async def test_add_first_floor_without_trims_data_uses_zero(flow):
    """The first floor gets zero trims when no trims_data exists."""
    await flow.async_step_add_floor({CONF_FLOOR_NAME: "floor_0"})
    trims = flow.floors_data["floor_0"]["trims"]
    assert [trims[k] for k in ("trim_up", "trim_down", "trim_left", "trim_right")] == [0] * 4
    assert flow.floors_data["floor_0"]["map_name"] == ""


async def test_add_next_floor_uses_user_trims(make_flow):
    """The next floors take the trims entered in the form."""
    flow = make_flow({"floors_data": {"floor_0": make_floor("floor_0")}})
    await flow.async_step_add_floor(
        {
            CONF_FLOOR_NAME: "floor_1",
            CONF_MAP_NAME: "Upstairs",
            CONF_TRIM_UP: 5,
            CONF_TRIM_DOWN: 6,
            CONF_TRIM_LEFT: 7,
            CONF_TRIM_RIGHT: 8,
        }
    )
    assert set(flow.floors_data) == {"floor_0", "floor_1"}
    trims = flow.floors_data["floor_1"]["trims"]
    assert (trims["trim_up"], trims["trim_down"]) == (5, 6)
    assert (trims["trim_left"], trims["trim_right"]) == (7, 8)
    assert flow.floors_data["floor_1"]["map_name"] == "Upstairs"
    assert flow.current_floor == "floor_1"
    assert flow.camera_options[CONF_FLOORS_DATA] == flow.floors_data


async def test_add_floor_does_not_mutate_config_entry_options(make_flow, config_entry):
    """Adding a floor leaves the config entry options untouched."""
    flow = make_flow({"floors_data": {"floor_0": make_floor("floor_0")}})
    await flow.async_step_add_floor({CONF_FLOOR_NAME: "floor_1"})
    assert set(config_entry.options["floors_data"]) == {"floor_0"}


async def test_add_floor_form_description(make_flow):
    """The add floor form description depends on the existing floors."""
    with patch.object(MQTTCameraOptionsFlowHandler, "_get_ha_floors", return_value=[]):
        first = await make_flow().async_step_add_floor()
        later = await make_flow(
            {"floors_data": {"floor_0": make_floor("floor_0")}}
        ).async_step_add_floor()
    assert_step(first, "add_floor")
    assert first["description_placeholders"]["info"] == (
        "Add a new floor. Existing auto-calculated trim values will be used for this first floor."
    )
    assert later["description_placeholders"]["info"] == (
        "Add a new floor. Enter trim values or leave at 0 to auto-calculate "
        "when you use 'Save Map Trims'."
    )


async def test_edit_floor_aborts_without_floors(flow):
    """Edit floor aborts when no floor is configured."""
    result = await flow.async_step_edit_floor()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_floors"


async def test_edit_floor_two_step_flow(make_flow):
    """Edit floor first selects the floor, then updates its map name and trims."""
    flow = make_flow({"floors_data": {"floor_0": make_floor("floor_0", "Old", 4)}})
    with patch.object(flow, "_get_ha_floors", return_value=[]):
        first = await flow.async_step_edit_floor()
        assert_step(first, "edit_floor")
        assert first["description_placeholders"] == {"floor_name": "", "trim_info": ""}

        second = await flow.async_step_edit_floor({CONF_FLOOR_NAME: "floor_0"})
    assert flow.selected_floor == "floor_0"
    assert_step(second, "edit_floor")
    assert second["description_placeholders"] == {
        "floor_name": "floor_0",
        "trim_info": "Current trims: 4, 0, 0, 0",
    }

    done = await flow.async_step_edit_floor(
        {
            CONF_MAP_NAME: "New",
            CONF_TRIM_UP: 1,
            CONF_TRIM_DOWN: 2,
            CONF_TRIM_LEFT: 3,
            CONF_TRIM_RIGHT: 4,
        }
    )
    expected = {
        "floor_0": {
            "trims": {
                "floor": "floor_0",
                "trim_up": 1,
                "trim_left": 3,
                "trim_down": 2,
                "trim_right": 4,
            },
            "map_name": "New",
            "rotation": 0,
        }
    }
    assert flow.floors_data == expected
    assert flow.camera_options == {CONF_FLOORS_DATA: expected}
    assert flow.selected_floor is None
    assert done["step_id"] == "floor_management"


async def test_delete_floor_aborts_without_floors(flow):
    """Delete floor aborts when no floor is configured."""
    result = await flow.async_step_delete_floor()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_floors"


async def test_delete_floor_form(make_flow):
    """The delete floor form is shown without input."""
    flow = make_flow({"floors_data": {"floor_0": make_floor("floor_0")}})
    with patch.object(flow, "_get_ha_floors", return_value=[]):
        result = await flow.async_step_delete_floor()
    assert_step(result, "delete_floor")


async def test_delete_other_floor_keeps_current(make_flow):
    """Deleting another floor keeps the current floor."""
    flow = make_flow(
        {
            "floors_data": {"a": make_floor("a"), "b": make_floor("b")},
            "current_floor": "a",
        }
    )
    result = await flow.async_step_delete_floor({CONF_FLOOR_NAME: "b"})
    assert list(flow.floors_data) == ["a"]
    assert flow.current_floor == "a"
    assert flow.camera_options == {
        CONF_FLOORS_DATA: flow.floors_data,
        CONF_CURRENT_FLOOR: "a",
    }
    assert result["step_id"] == "floor_management"


async def test_delete_current_floor_picks_first_remaining(make_flow):
    """Deleting the current floor selects the first remaining floor."""
    flow = make_flow(
        {
            "floors_data": {"a": make_floor("a"), "b": make_floor("b"), "c": make_floor("c")},
            "current_floor": "a",
        }
    )
    await flow.async_step_delete_floor({CONF_FLOOR_NAME: "a"})
    assert list(flow.floors_data) == ["b", "c"]
    assert flow.current_floor == "b"
    assert flow.camera_options[CONF_CURRENT_FLOOR] == "b"


async def test_delete_last_floor_uses_first_ha_floor(make_flow):
    """Deleting the last floor selects the first Home Assistant floor."""
    flow = make_flow({"floors_data": {"a": make_floor("a")}, "current_floor": "a"})
    with patch.object(flow, "_get_ha_floors", return_value=HA_FLOORS):
        await flow.async_step_delete_floor({CONF_FLOOR_NAME: "a"})
    assert flow.floors_data == {}
    assert flow.current_floor == "a"  # first HA floor id


async def test_delete_last_floor_without_ha_floors_defaults(make_flow):
    """Deleting the last floor without Home Assistant floors selects floor_0."""
    flow = make_flow({"floors_data": {"a": make_floor("a")}, "current_floor": "a"})
    with patch.object(flow, "_get_ha_floors", return_value=[]):
        await flow.async_step_delete_floor({CONF_FLOOR_NAME: "a"})
    assert flow.floors_data == {}
    assert flow.current_floor == "floor_0"


async def test_delete_unknown_floor_shows_form_again(make_flow):
    """Deleting an unknown floor shows the form again and changes nothing."""
    flow = make_flow({"floors_data": {"a": make_floor("a")}, "current_floor": "a"})
    with patch.object(flow, "_get_ha_floors", return_value=[]):
        result = await flow.async_step_delete_floor({CONF_FLOOR_NAME: "zzz"})
    assert_step(result, "delete_floor")
    assert list(flow.floors_data) == ["a"]
    assert flow.camera_options == {}


# --- update_floor_data ----------------------------------------------------


def make_coordinator(flow, config_entry, trims):
    """Register a mocked coordinator returning the given trims in hass.data."""
    coordinator = MagicMock()
    coordinator.context.shared.trims.to_dict.return_value = trims
    flow.hass.data = {DOMAIN: {config_entry.entry_id: {"coordinator": coordinator}}}
    return coordinator


async def test_update_floor_data_stores_coordinator_trims(make_flow, config_entry):
    """Update floor data stores the coordinator trims and the stored rotation."""
    flow = make_flow(
        {
            "floors_data": {"a": make_floor("a", "Kitchen")},
            "current_floor": "a",
            "rotate_image": "180",
        }
    )
    make_coordinator(
        flow,
        config_entry,
        {"trim_up": 10, "trim_left": 20, "trim_down": 30, "trim_right": 40},
    )
    flow.async_step_edit_floor = AsyncMock(return_value="edit_result")

    result = await flow.async_step_update_floor_data()

    assert result == "edit_result"
    stored = flow.floors_data["a"]
    assert stored["map_name"] == "Kitchen"
    assert stored["rotation"] == 180
    assert stored["trims"] == {
        "floor": "a",
        "trim_up": 10,
        "trim_left": 20,
        "trim_down": 30,
        "trim_right": 40,
    }
    assert flow.camera_options["floors_data"] == flow.floors_data
    assert flow.camera_options["current_floor"] == "a"
    assert flow.camera_options["trims_data"] == stored["trims"]


async def test_update_floor_data_prefers_pending_rotation(make_flow, config_entry):
    """Update floor data uses the rotation changed in this session first."""
    flow = make_flow(
        {"floors_data": {"a": make_floor("a")}, "current_floor": "a", "rotate_image": "180"}
    )
    flow.camera_options["rotate_image"] = "90"
    make_coordinator(flow, config_entry, {})
    flow.async_step_edit_floor = AsyncMock()
    await flow.async_step_update_floor_data()
    assert flow.floors_data["a"]["rotation"] == 90
    assert flow.floors_data["a"]["trims"]["trim_up"] == 0


async def test_update_floor_data_without_floors_changes_nothing(flow, config_entry):
    """Update floor data changes nothing when no floor is configured."""
    make_coordinator(flow, config_entry, {})
    flow.async_step_edit_floor = AsyncMock(return_value="edit_result")
    assert await flow.async_step_update_floor_data() == "edit_result"
    assert flow.camera_options == {}


# --- save -----------------------------------------------------------------


async def test_save_options_creates_entry(flow):
    """Save options merges the options and creates the config entry."""
    flow.camera_options = {"robot_size": 5}
    flow.backup_options = {"old": 1}
    with patch(f"{MODULE}.update_options", AsyncMock(return_value={"merged": 1})) as update:
        result = await flow.async_step_save_options()
    update.assert_awaited_once_with({"old": 1}, {"robot_size": 5})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"] == {"merged": 1}


@pytest.mark.parametrize(
    ("error", "reason"),
    [(ConfigEntryError("x"), "config_error"), (ConfigEntryNotReady("x"), "not_ready")],
)
async def test_save_options_aborts_on_errors(flow, error, reason):
    """Save options aborts with the reason matching the raised error."""
    with patch(f"{MODULE}.update_options", AsyncMock(side_effect=error)):
        result = await flow.async_step_save_options()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == reason

"""
Options flow handler for MQTT Vacuum Camera integration.
Last Updated on version: 2025.10.0
"""

from copy import deepcopy
from typing import Any, Dict, Optional

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    floor_registry as fr,
)
from homeassistant.helpers.selector import (
    BooleanSelector,
    ColorRGBSelector,
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from valetudo_map_parser import FloorData, TrimsData
from valetudo_map_parser.config.types import RoomStore
import voluptuous as vol

from .common import extract_file_name, update_options
from .const import (
    ALPHA_BACKGROUND,
    ALPHA_CARPET,
    ALPHA_CHARGER,
    ALPHA_GO_TO,
    ALPHA_MATERIAL_TILE,
    ALPHA_MATERIAL_WOOD,
    ALPHA_MOVE,
    ALPHA_NO_GO,
    ALPHA_ROBOT,
    ALPHA_ROOM_0,
    ALPHA_TEXT,
    ALPHA_VALUES,
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
    CONF_DISABLE_CARPETS,
    CONF_DISABLE_MATERIAL_OVERLAY,
    CONF_FLOOR_NAME,
    CONF_FLOORS_DATA,
    CONF_MAP_NAME,
    CONF_OFFSET_BOTTOM,
    CONF_OFFSET_LEFT,
    CONF_OFFSET_RIGHT,
    CONF_OFFSET_TOP,
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
    DEFAULT_ROOMS,
    DEFAULT_ROOMS_NAMES,
    DOMAIN,
    DRAW_FLAGS,
    FONTS_AVAILABLE,
    IS_ALPHA,
    IS_ALPHA_R1,
    IS_ALPHA_R2,
    LOGGER,
    RATIO_VALUES,
    ROBOT_SIZE_VALUES,
    ROOM_FLAGS,
    ROTATION_VALUES,
    TEXT_SIZE_VALUES,
)


# noinspection PyTypeChecker
class MQTTCameraOptionsFlowHandler(OptionsFlow):
    """Options flow handler for MQTT Vacuum Camera integration."""

    def __init__(self, config_entry: ConfigEntry):
        """Initialize options flow."""
        if not config_entry:
            raise ConfigEntryError("Config entry is required.")
        self.camera_config = config_entry
        self.unique_id = self.camera_config.unique_id
        self.camera_options = {}
        self.backup_options = deepcopy(dict(self.camera_config.options))
        self.file_name = extract_file_name(self.unique_id)
        self.is_alpha_enabled = False
        self.number_of_rooms = DEFAULT_ROOMS
        self.rooms_placeholders = DEFAULT_ROOMS_NAMES
        self.floors_data = dict(self.camera_config.options.get("floors_data", {}))
        self.current_floor = self.camera_config.options.get("current_floor", "floor_0")
        self.selected_floor = None
        LOGGER.debug(
            "Options edit in progress.. options before edit: %s",
            dict(self.backup_options),
        )
        options_values = list(self.camera_config.options.values())
        if len(options_values) > 0:
            self.config_dict: NumberSelectorConfig = ALPHA_VALUES
            config_size: NumberSelectorConfig = TEXT_SIZE_VALUES
            robot_size_selector: NumberSelectorConfig = ROBOT_SIZE_VALUES
            font_selector = SelectSelectorConfig(
                options=FONTS_AVAILABLE,
                mode=SelectSelectorMode.DROPDOWN,
            )
            rotation_selector = SelectSelectorConfig(
                options=ROTATION_VALUES,
                mode=SelectSelectorMode.DROPDOWN,
            )
            aspec_ratio_selector = SelectSelectorConfig(
                options=RATIO_VALUES,
                mode=SelectSelectorMode.DROPDOWN,
            )
            self.image_schema = vol.Schema(
                {
                    vol.Required(
                        ATTR_ROTATE, default=config_entry.options.get("rotate_image")
                    ): SelectSelector(rotation_selector),
                    vol.Optional(
                        ATTR_MARGINS, default=config_entry.options.get("margins")
                    ): cv.string,
                    vol.Required(
                        CONF_ASPECT_RATIO,
                        default=config_entry.options.get("aspect_ratio"),
                    ): SelectSelector(aspec_ratio_selector),
                    vol.Optional(
                        CONF_ZOOM_LOCK_RATIO,
                        default=config_entry.options.get("zoom_lock_ratio"),
                    ): BooleanSelector(),
                    vol.Optional(
                        CONF_AUTO_ZOOM,
                        default=config_entry.options.get("auto_zoom"),
                    ): BooleanSelector(),
                    vol.Optional(
                        CONF_ROBOT_SIZE,
                        default=config_entry.options.get("robot_size"),
                    ): NumberSelector(robot_size_selector),
                }
            )
            self.image_schema_2 = vol.Schema(
                {
                    vol.Optional(
                        CONF_OFFSET_TOP, default=config_entry.options.get("offset_top")
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_OFFSET_BOTTOM,
                        default=config_entry.options.get("offset_bottom"),
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_OFFSET_LEFT,
                        default=config_entry.options.get("offset_left"),
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_OFFSET_RIGHT,
                        default=config_entry.options.get("offset_right"),
                    ): cv.positive_int,
                }
            )
            self.status_text_options = vol.Schema(
                {
                    vol.Optional(
                        CONF_VAC_STAT,
                        default=config_entry.options.get("show_vac_status"),
                    ): BooleanSelector(),
                    vol.Optional(
                        CONF_VAC_STAT_FONT,
                        default=config_entry.options.get("vac_status_font"),
                    ): SelectSelector(font_selector),
                    vol.Optional(
                        CONF_VAC_STAT_SIZE,
                        default=config_entry.options.get("vac_status_size"),
                    ): NumberSelector(config_size),
                    vol.Optional(
                        CONF_VAC_STAT_POS,
                        default=config_entry.options.get("vac_status_position"),
                    ): BooleanSelector(),
                    vol.Optional(
                        COLOR_TEXT, default=config_entry.options.get("color_text")
                    ): ColorRGBSelector(),
                }
            )
            self.colors_base_schema = vol.Schema(
                {
                    vol.Optional(
                        COLOR_BACKGROUND,
                        default=config_entry.options.get("color_background"),
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ZONE_CLEAN,
                        default=config_entry.options.get("color_zone_clean"),
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_WALL, default=config_entry.options.get("color_wall")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROBOT, default=config_entry.options.get("color_robot")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_CHARGER, default=config_entry.options.get("color_charger")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_MOVE, default=config_entry.options.get("color_move")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_GO_TO, default=config_entry.options.get("color_go_to")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_NO_GO, default=config_entry.options.get("color_no_go")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        IS_ALPHA, default=self.is_alpha_enabled
                    ): BooleanSelector(),
                }
            )
            self.colors_alpha_1_schema = vol.Schema(
                {
                    vol.Optional(
                        ALPHA_BACKGROUND,
                        default=config_entry.options.get("alpha_background"),
                    ): NumberSelector(self.config_dict),
                    vol.Optional(
                        ALPHA_ZONE_CLEAN,
                        default=config_entry.options.get("alpha_zone_clean"),
                    ): NumberSelector(self.config_dict),
                    vol.Optional(
                        ALPHA_WALL, default=config_entry.options.get("alpha_wall")
                    ): NumberSelector(self.config_dict),
                    vol.Optional(
                        ALPHA_ROBOT, default=config_entry.options.get("alpha_robot")
                    ): NumberSelector(self.config_dict),
                    vol.Optional(
                        ALPHA_CHARGER, default=config_entry.options.get("alpha_charger")
                    ): NumberSelector(self.config_dict),
                    vol.Optional(
                        ALPHA_MOVE, default=config_entry.options.get("alpha_move")
                    ): NumberSelector(self.config_dict),
                    vol.Optional(
                        ALPHA_GO_TO, default=config_entry.options.get("alpha_go_to")
                    ): NumberSelector(self.config_dict),
                    vol.Optional(
                        ALPHA_NO_GO, default=config_entry.options.get("alpha_no_go")
                    ): NumberSelector(self.config_dict),
                    vol.Optional(
                        ALPHA_TEXT, default=config_entry.options.get("alpha_text")
                    ): NumberSelector(self.config_dict),
                }
            )

    def _get_ha_floor_names(self) -> list[str]:
        """Get list of floor names configured in Home Assistant."""
        try:
            floor_reg = fr.async_get(self.hass)
            floors = list(floor_reg.async_list_floors())
            return [floor.name for floor in floors] if floors else []
        except Exception as e:
            LOGGER.warning("Failed to get HA floor names: %s", e)
            return []

    def _get_ha_floor_id_by_name(self, floor_name: str) -> str:
        """Get floor ID from floor name."""
        try:
            floor_reg = fr.async_get(self.hass)
            floors = list(floor_reg.async_list_floors())
            for floor in floors:
                if floor.name == floor_name:
                    return floor.floor_id
            # If not found, return the name as-is (might be floor_0 or custom)
            return floor_name
        except Exception as e:
            LOGGER.warning("Failed to get floor ID for name %s: %s", floor_name, e)
            return floor_name

    def _log_floor_area_data(self) -> None:
        """Log all floors and their associated areas for debugging."""
        try:
            floor_reg = fr.async_get(self.hass)
            area_reg = ar.async_get(self.hass)

            floors = list(floor_reg.async_list_floors())

            if not floors:
                LOGGER.info("No floors configured in Home Assistant")
                return

            LOGGER.info("=" * 60)
            LOGGER.info("HOME ASSISTANT FLOOR & AREA CONFIGURATION")
            LOGGER.info("=" * 60)

            for floor in floors:
                LOGGER.info(
                    "Floor: %s (ID: %s, Level: %s, Icon: %s)",
                    floor.name,
                    floor.floor_id,
                    floor.level if floor.level is not None else "N/A",
                    floor.icon if floor.icon else "N/A",
                )

                # Get areas for this floor
                areas = ar.async_entries_for_floor(area_reg, floor.floor_id)

                if areas:
                    LOGGER.info("  Areas on this floor:")
                    for area in areas:
                        LOGGER.info(
                            "    - %s (ID: %s, Icon: %s)",
                            area.name,
                            area.id,
                            area.icon if area.icon else "N/A",
                        )
                else:
                    LOGGER.info("  No areas assigned to this floor")

                LOGGER.info("-" * 60)

            # Also log areas without floor assignment
            all_areas = list(area_reg.async_list_areas())
            unassigned_areas = [area for area in all_areas if area.floor_id is None]

            if unassigned_areas:
                LOGGER.info("Areas NOT assigned to any floor:")
                for area in unassigned_areas:
                    LOGGER.info(
                        "  - %s (ID: %s, Icon: %s)",
                        area.name,
                        area.id,
                        area.icon if area.icon else "N/A",
                    )
                LOGGER.info("-" * 60)

            LOGGER.info("=" * 60)

        except Exception as e:
            LOGGER.warning("Failed to retrieve floor/area data: %s", e, exc_info=True)

    # pylint: disable=unused-argument
    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Start the options menu configuration."""
        LOGGER.info("%s: Options Configuration Started.", self.camera_config.unique_id)

        # Log floor and area configuration
        self._log_floor_area_data()

        errors = {}

        rooms_data = RoomStore(self.file_name)
        self.number_of_rooms = rooms_data.get_rooms_count()
        self.rooms_placeholders = (
            rooms_data.room_names if rooms_data.room_names else DEFAULT_ROOMS_NAMES
        )
        LOGGER.debug("Rooms count: %s", self.number_of_rooms)
        if (
            not isinstance(self.number_of_rooms, int)
            or self.number_of_rooms < DEFAULT_ROOMS
        ):
            errors["base"] = "no_rooms"
            LOGGER.error("No rooms found in the configuration. Aborting.")
            return self.async_abort(reason="no_rooms")

        return self.async_show_menu(
            step_id="init",
            menu_options=["image_opt", "colours", "materials", "floor_management", "save_options"],
        )

    # pylint: disable=unused-argument
    async def async_step_main_menu(self, user_input=None) -> ConfigFlowResult:
        """Return to main menu."""
        return await self.async_step_init()

    # pylint: disable=unused-argument
    async def async_step_image_opt(self, user_input=None) -> ConfigFlowResult:
        """Handle image options menu."""
        return self.async_show_menu(
            step_id="image_opt",
            menu_options=[
                "image_basic_opt",
                "status_text",
                "draw_elements",
                "main_menu",
            ],
        )

    async def async_step_draw_elements(self, user_input=None) -> ConfigFlowResult:
        """Handle draw elements menu."""
        return self.async_show_menu(
            step_id="draw_elements",
            menu_options=[
                "map_elements",
                "segments_visibility",
                "main_menu",
            ],
        )

    # pylint: disable=unused-argument
    async def async_step_colours(self, user_input=None) -> ConfigFlowResult:
        """Handle colours menu."""
        menu_options = ["base_colours"]

        match self.number_of_rooms:
            case 1:
                menu_options.append("floor_only")
            case n if 1 < n <= 8:
                menu_options.extend(["rooms_colours_1"])
            case _:
                menu_options.extend(["rooms_colours_1", "rooms_colours_2"])

        if self.is_alpha_enabled:
            menu_options.append("transparency")

        menu_options.append("main_menu")

        return self.async_show_menu(
            step_id="colours",
            menu_options=menu_options,
        )

    async def async_step_transparency(self, user_input=None) -> ConfigFlowResult:
        """Handle transparency menu"""

        menu_options = ["alpha_1"]

        if self.number_of_rooms == 1:
            menu_options.append("alpha_floor")
        elif self.number_of_rooms <= 8:
            menu_options.append("alpha_2")
        else:
            menu_options.extend(["alpha_2", "alpha_3"])

        menu_options.append("main_menu")

        return self.async_show_menu(
            step_id="transparency",
            menu_options=menu_options,
        )



    async def async_step_materials(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Handle materials configuration."""
        if user_input is not None:
            self.camera_options.update(
                {
                    "disable_material_overlay": user_input.get(
                        CONF_DISABLE_MATERIAL_OVERLAY
                    ),
                    "disable_carpets": user_input.get(CONF_DISABLE_CARPETS),
                    "color_carpet": user_input.get(COLOR_CARPET),
                    "color_material_wood": user_input.get(COLOR_MATERIAL_WOOD),
                    "color_material_tile": user_input.get(COLOR_MATERIAL_TILE),
                    "alpha_carpet": user_input.get(ALPHA_CARPET),
                    "alpha_material_wood": user_input.get(ALPHA_MATERIAL_WOOD),
                    "alpha_material_tile": user_input.get(ALPHA_MATERIAL_TILE),
                }
            )
            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_DISABLE_MATERIAL_OVERLAY,
                    default=self.camera_config.options.get(
                        "disable_material_overlay", False
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_DISABLE_CARPETS,
                    default=self.camera_config.options.get("disable_carpets", False),
                ): BooleanSelector(),
                vol.Optional(
                    COLOR_CARPET,
                    default=self.camera_config.options.get("color_carpet"),
                ): ColorRGBSelector(),
                vol.Optional(
                    COLOR_MATERIAL_WOOD,
                    default=self.camera_config.options.get("color_material_wood"),
                ): ColorRGBSelector(),
                vol.Optional(
                    COLOR_MATERIAL_TILE,
                    default=self.camera_config.options.get("color_material_tile"),
                ): ColorRGBSelector(),
                vol.Optional(
                    ALPHA_CARPET,
                    default=self.camera_config.options.get("alpha_carpet"),
                ): NumberSelector(self.config_dict),
                vol.Optional(
                    ALPHA_MATERIAL_WOOD,
                    default=self.camera_config.options.get("alpha_material_wood"),
                ): NumberSelector(self.config_dict),
                vol.Optional(
                    ALPHA_MATERIAL_TILE,
                    default=self.camera_config.options.get("alpha_material_tile"),
                ): NumberSelector(self.config_dict),
            }
        )

        return self.async_show_form(
            step_id="materials",
            data_schema=schema,
        )

    # Image Settings Steps
    async def async_step_image_basic_opt(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """Handle basic image settings."""
        if user_input is not None:
            self.camera_options.update(
                {
                    "rotate_image": user_input.get(ATTR_ROTATE),
                    "margins": user_input.get(ATTR_MARGINS),
                    "aspect_ratio": user_input.get(CONF_ASPECT_RATIO),
                    "zoom_lock_ratio": user_input.get(CONF_ZOOM_LOCK_RATIO),
                    "auto_zoom": user_input.get(CONF_AUTO_ZOOM),
                    "robot_size": user_input.get(CONF_ROBOT_SIZE),
                }
            )
            return await self.async_step_image_opt()

        return self.async_show_form(
            step_id="image_basic_opt",
            data_schema=self.image_schema,
            description_placeholders=self.camera_options,
        )

    async def async_step_floor_management(self, user_input=None) -> ConfigFlowResult:
        """Handle floor management menu."""
        return self.async_show_menu(
            step_id="floor_management",
            menu_options=[
                "select_floor",
                "add_floor",
                "edit_floor",
                "delete_floor",
                "main_menu",
            ],
        )

    async def async_step_map_trims(self, user_input=None) -> ConfigFlowResult:
        """Handle map trims settings."""
        return self.async_show_menu(
            step_id="map_trims",
            menu_options=[
                "reset_map_trims",
                "save_map_trims",
                "main_menu",
            ],
        )



    async def async_step_status_text(self, user_input: Optional[Dict[str, Any]] = None):
        """Handle status text settings."""
        if user_input is not None:
            self.camera_options.update(
                {
                    "show_vac_status": user_input.get(CONF_VAC_STAT),
                    "vac_status_font": user_input.get(CONF_VAC_STAT_FONT),
                    "vac_status_size": user_input.get(CONF_VAC_STAT_SIZE),
                    "vac_status_position": user_input.get(CONF_VAC_STAT_POS),
                    "color_text": user_input.get(COLOR_TEXT),
                }
            )
            return await self.async_step_image_opt()

        return self.async_show_form(
            step_id="status_text",
            data_schema=self.status_text_options,
            description_placeholders=self.camera_options,
        )

    def _build_boolean_options_fields(self, flags, limit=None):
        """Helper method to build boolean option fields from a list of flags.

        Args:
            flags: List of flag constants to use for building fields
            limit: Optional limit on the number of flags to use (for rooms)

        Returns:
            Dictionary of fields for the form schema
        """
        fields = {}
        flags_to_use = flags

        # If limit is provided, only use that many flags
        if limit is not None:
            flags_to_use = flags[:limit]

        for flag in flags_to_use:
            fields[
                vol.Optional(
                    flag,
                    default=self.camera_config.options.get(flag, False),
                )
            ] = BooleanSelector()

        return fields

    @staticmethod
    def _update_boolean_options(user_input, flags, limit=None):
        """Helper method to update options based on user input.

        Args:
            user_input: User input from the form
            flags: List of flag constants to use for updating options
            limit: Optional limit on the number of flags to use (for rooms)

        Returns:
            Dictionary of updated options
        """
        options_update = {}
        flags_to_use = flags

        # If limit is provided, only use that many flags
        if limit is not None:
            flags_to_use = flags[:limit]

        for flag in flags_to_use:
            options_update[flag] = user_input.get(flag, False)

        return options_update

    async def async_step_map_elements(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """Handle map elements visibility configuration."""
        LOGGER.info("Map Elements Configuration Started.")

        if user_input is not None:
            # Update options based on user input using DRAW_FLAGS
            options_update = self._update_boolean_options(user_input, DRAW_FLAGS)
            self.camera_options.update(options_update)
            return await self.async_step_draw_elements()

        # Create schema for the form using DRAW_FLAGS
        fields = self._build_boolean_options_fields(DRAW_FLAGS)

        return self.async_show_form(
            step_id="map_elements",
            data_schema=vol.Schema(fields),
            description_placeholders=self.rooms_placeholders,
        )

    async def async_step_segments_visibility(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """Handle segments (rooms) visibility configuration."""
        LOGGER.info("Segments Visibility Configuration Started.")

        # Limit to the number of rooms that exist
        room_limit = min(self.number_of_rooms, 15)

        if user_input is not None:
            # Update options based on user input using ROOM_FLAGS
            options_update = self._update_boolean_options(
                user_input, ROOM_FLAGS, room_limit
            )
            self.camera_options.update(options_update)
            return await self.async_step_draw_elements()

        # Create schema for the form - only show fields for rooms that exist
        fields = self._build_boolean_options_fields(ROOM_FLAGS, room_limit)

        return self.async_show_form(
            step_id="segments_visibility",
            data_schema=vol.Schema(fields),
            description_placeholders=self.rooms_placeholders,
        )

    async def async_step_base_colours(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """
        Base Colours Configuration.
        """
        LOGGER.debug("Base Colours Configuration Started")
        if user_input is not None:
            self.camera_options.update(
                {
                    "color_charger": user_input.get(COLOR_CHARGER),
                    "color_move": user_input.get(COLOR_MOVE),
                    "color_wall": user_input.get(COLOR_WALL),
                    "color_robot": user_input.get(COLOR_ROBOT),
                    "color_go_to": user_input.get(COLOR_GO_TO),
                    "color_no_go": user_input.get(COLOR_NO_GO),
                    "color_zone_clean": user_input.get(COLOR_ZONE_CLEAN),
                    "color_background": user_input.get(COLOR_BACKGROUND),
                }
            )
            self.is_alpha_enabled = user_input.get(IS_ALPHA)
            if self.is_alpha_enabled:
                self.is_alpha_enabled = False
                return await self.async_step_alpha_1()
            return await self.async_step_colours()

        return self.async_show_form(
            step_id="base_colours",
            data_schema=self.colors_base_schema,
            description_placeholders=self.camera_options,
        )

    async def async_step_alpha_1(self, user_input: Optional[Dict[str, Any]] = None):
        """
        Transparency Configuration for the Base Colours
        """
        LOGGER.debug("Base Colours Alpha Configuration Started")
        if user_input is not None:
            self.camera_options.update(
                {
                    "alpha_charger": user_input.get(ALPHA_CHARGER),
                    "alpha_move": user_input.get(ALPHA_MOVE),
                    "alpha_wall": user_input.get(ALPHA_WALL),
                    "alpha_robot": user_input.get(ALPHA_ROBOT),
                    "alpha_go_to": user_input.get(ALPHA_GO_TO),
                    "alpha_no_go": user_input.get(ALPHA_NO_GO),
                    "alpha_zone_clean": user_input.get(ALPHA_ZONE_CLEAN),
                    "alpha_background": user_input.get(ALPHA_BACKGROUND),
                    "alpha_text": user_input.get(ALPHA_TEXT),
                }
            )
            return await self.async_step_transparency()

        return self.async_show_form(
            step_id="alpha_1",
            data_schema=self.colors_alpha_1_schema,
            description_placeholders=self.camera_options,
        )

    async def async_step_floor_only(self, user_input: Optional[Dict[str, Any]] = None):
        """Floor colours configuration step based on one room only"""
        LOGGER.info("Floor Colour Configuration Started.")

        if user_input is not None:
            # Update options based on user input
            self.camera_options.update({"color_room_0": user_input.get(COLOR_ROOM_0)})
            self.is_alpha_enabled = user_input.get(IS_ALPHA_R1, False)
            if self.is_alpha_enabled:
                return await self.async_step_alpha_floor()
            return await self.async_step_colours()

        fields = {
            vol.Optional(
                COLOR_ROOM_0, default=self.camera_config.options.get("color_room_0")
            ): ColorRGBSelector(),
            vol.Optional(IS_ALPHA_R1, default=self.is_alpha_enabled): BooleanSelector(),
        }

        return self.async_show_form(
            step_id="floor_only",
            data_schema=vol.Schema(fields),
            description_placeholders=self.camera_options,
        )

    async def async_step_rooms_colours_1(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """Dynamically generate rooms colours configuration step based on the number of rooms."""
        LOGGER.info("Dynamic Rooms Colours Configuration Started.")
        rooms_count = 1
        if self.number_of_rooms > 8:
            rooms_count = 8
        elif (self.number_of_rooms <= 8) and (self.number_of_rooms != 0):
            rooms_count = self.number_of_rooms

        if user_input is not None:
            # Update options based on user input
            for i in range(rooms_count):
                room_key = f"color_room_{i}"
                self.camera_options.update({room_key: user_input.get(room_key)})

            self.is_alpha_enabled = user_input.get(IS_ALPHA_R1, False)

            if self.is_alpha_enabled:
                return await self.async_step_alpha_2()
            return await self.async_step_colours()

        # Dynamically create data schema based on the number of rooms
        fields = {}
        for i in range(rooms_count):
            fields[
                vol.Optional(
                    f"color_room_{i}",
                    default=self.camera_config.options.get(f"color_room_{i}"),
                )
            ] = ColorRGBSelector()

        fields[vol.Optional(IS_ALPHA_R1, default=self.is_alpha_enabled)] = (
            BooleanSelector()
        )

        return self.async_show_form(
            step_id="rooms_colours_1",
            data_schema=vol.Schema(fields),
            description_placeholders=self.rooms_placeholders,
        )

    async def async_step_rooms_colours_2(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """Dynamically generate rooms colours configuration step based on the number of rooms."""
        LOGGER.info("Dynamic Rooms Colours over 8 Configuration Started.")
        if user_input is not None:
            # Update options based on user input
            for i in range(8, min(self.number_of_rooms, 16)):
                room_key = f"color_room_{i}"
                self.camera_options.update({room_key: user_input.get(room_key)})

            self.is_alpha_enabled = user_input.get(IS_ALPHA_R2, False)

            if self.is_alpha_enabled:
                return await self.async_step_alpha_3()
            return await self.async_step_colours()

        # Dynamically create data schema based on the number of rooms
        fields = {}
        for i in range(8, min(self.number_of_rooms, 16)):
            fields[
                vol.Optional(
                    f"color_room_{i}",
                    default=self.camera_config.options.get(f"color_room_{i}"),
                )
            ] = ColorRGBSelector()

        fields[vol.Optional(IS_ALPHA_R2, default=self.is_alpha_enabled)] = (
            BooleanSelector()
        )

        return self.async_show_form(
            step_id="rooms_colours_2",
            data_schema=vol.Schema(fields),
            description_placeholders=self.rooms_placeholders,
        )

    async def async_step_alpha_floor(self, user_input: Optional[Dict[str, Any]] = None):
        """Floor alpha configuration step based on one room only"""
        LOGGER.info("Floor Alpha Configuration Started.")

        if user_input is not None:
            # Update options based on user input
            self.camera_options.update({"alpha_room_0": user_input.get(ALPHA_ROOM_0)})
            return await self.async_step_transparency()

        fields = {
            vol.Optional(
                ALPHA_ROOM_0, default=self.camera_config.options.get("alpha_room_0")
            ): NumberSelector(self.config_dict),
        }

        return self.async_show_form(
            step_id="alpha_floor",
            data_schema=vol.Schema(fields),
            description_placeholders=self.rooms_placeholders,
        )

    async def async_step_alpha_2(self, user_input: Optional[Dict[str, Any]] = None):
        """Dynamically generate rooms colours configuration step based on the number of rooms."""
        LOGGER.info("Dynamic Rooms 1 to 8 Alpha Configuration Started.")
        rooms_count = 1
        if self.number_of_rooms > 8:
            rooms_count = 8
        elif (self.number_of_rooms <= 8) and (self.number_of_rooms != 0):
            rooms_count = self.number_of_rooms

        if user_input is not None:
            # Update options based on user input
            for i in range(rooms_count):
                room_key = f"alpha_room_{i}"
                self.camera_options.update({room_key: user_input.get(room_key)})

            return await self.async_step_transparency()

        # Dynamically create data schema based on the number of rooms
        fields = {}
        for i in range(rooms_count):
            fields[
                vol.Optional(
                    f"alpha_room_{i}",
                    default=self.camera_config.options.get(f"alpha_room_{i}"),
                )
            ] = NumberSelector(self.config_dict)

        return self.async_show_form(
            step_id="alpha_2",
            data_schema=vol.Schema(fields),
            description_placeholders=self.rooms_placeholders,
        )

    async def async_step_alpha_3(self, user_input: Optional[Dict[str, Any]] = None):
        """Dynamically generate rooms colours configuration step based on the number of rooms."""
        LOGGER.info("Dynamic Rooms Alpha up to 16 Configuration Started.")
        if user_input is not None:
            # Update options based on user input
            for i in range(8, min(self.number_of_rooms, 16)):
                room_key = f"alpha_room_{i}"
                self.camera_options.update({room_key: user_input.get(room_key)})

            return await self.async_step_transparency()

        # Dynamically create data schema based on the number of rooms
        fields = {}
        for i in range(8, min(self.number_of_rooms, 16)):
            fields[
                vol.Optional(
                    f"alpha_room_{i}",
                    default=self.camera_config.options.get(f"alpha_room_{i}"),
                )
            ] = NumberSelector(self.config_dict)

        return self.async_show_form(
            step_id="alpha_3",
            data_schema=vol.Schema(fields),
            description_placeholders=self.rooms_placeholders,
        )

    # Other Advanced Steps

    # pylint: disable=unused-argument
    async def async_step_reset_map_trims(self, user_input=None):
        """Handle map trims reset."""
        entry = self.camera_config.entry_id
        LOGGER.debug("Resetting the map trims for %s", entry)
        coordinator = self.hass.data[DOMAIN][entry]["coordinator"]

        # Always reset trims when this option is selected
        reset_trims = coordinator.context.shared.trims.clear()
        self.camera_options = {
            "offset_bottom": 0,
            "offset_left": 0,
            "offset_top": 0,
            "offset_right": 0,
            "trims_data": reset_trims,
        }
        return await self.async_step_save_options()

    # pylint: disable=unused-argument
    async def async_step_save_map_trims(self, user_input=None):
        """Handle map trims save."""
        entry = self.camera_config.entry_id
        LOGGER.debug("Saving the map trims for %s", entry)
        coordinator = self.hass.data[DOMAIN][entry]["coordinator"]

        # Save current trims from coordinator
        new_trims = coordinator.context.shared.trims.to_dict()
        self.camera_options = {"trims_data": new_trims}
        return await self.async_step_save_options()

    # Floor Management Steps

    async def async_step_select_floor(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Select the current active floor."""
        if user_input is not None:
            selected_floor_name = user_input.get(CONF_CURRENT_FLOOR)
            # Convert floor name to floor ID
            selected_floor_id = self._get_ha_floor_id_by_name(selected_floor_name)
            self.camera_options = {
                CONF_CURRENT_FLOOR: selected_floor_id,
            }
            LOGGER.info(
                "Selected floor: %s (ID: %s)", selected_floor_name, selected_floor_id
            )
            return await self.async_step_floor_management()

        # Get floor names from Home Assistant floor registry
        ha_floor_names = self._get_ha_floor_names()

        # Use HA floor names if available, otherwise fallback to "floor_0"
        floor_options = ha_floor_names if ha_floor_names else ["floor_0"]

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CURRENT_FLOOR, default=self.current_floor
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=floor_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="select_floor",
            data_schema=schema,
            description_placeholders={"current_floor": self.current_floor},
        )

    async def async_step_add_floor(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Add a new floor with trim settings."""
        if user_input is not None:
            floor_name = user_input.get(CONF_FLOOR_NAME)
            map_name = user_input.get(CONF_MAP_NAME, "")

            # Use existing trims_data as default for first floor if no floors exist yet
            if not self.floors_data:
                existing_trims = self.camera_config.options.get("trims_data", {})
                trim_up = existing_trims.get("trim_up", 0)
                trim_down = existing_trims.get("trim_down", 0)
                trim_left = existing_trims.get("trim_left", 0)
                trim_right = existing_trims.get("trim_right", 0)
                LOGGER.info(
                    "Using existing trims_data for first floor: %s", existing_trims
                )
            else:
                trim_up = user_input.get(CONF_TRIM_UP, 0)
                trim_down = user_input.get(CONF_TRIM_DOWN, 0)
                trim_left = user_input.get(CONF_TRIM_LEFT, 0)
                trim_right = user_input.get(CONF_TRIM_RIGHT, 0)

            # Create new floor data
            new_floor = FloorData(
                trims=TrimsData(
                    floor=floor_name,
                    trim_up=trim_up,
                    trim_down=trim_down,
                    trim_left=trim_left,
                    trim_right=trim_right,
                ),
                map_name=map_name,
            )

            # Update floors_data
            updated_floors = dict(self.floors_data)
            updated_floors[floor_name] = new_floor.to_dict()

            self.camera_options = {
                CONF_FLOORS_DATA: updated_floors,
                CONF_CURRENT_FLOOR: floor_name,  # Set as current floor
            }
            LOGGER.info("Added new floor: %s", floor_name)
            return await self.async_step_floor_management()

        # Get HA floor names for dropdown
        ha_floor_names = self._get_ha_floor_names()

        # Filter out already configured floors
        available_floors = [f for f in ha_floor_names if f not in self.floors_data]

        # If no HA floors or all are used, allow custom text input
        if available_floors:
            floor_selector = SelectSelector(
                SelectSelectorConfig(
                    options=available_floors,
                    mode=SelectSelectorMode.DROPDOWN,
                    custom_value=True,  # Allow custom input
                )
            )
        else:
            # Fallback to text input if no HA floors available
            floor_selector = TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_FLOOR_NAME): floor_selector,
                vol.Optional(CONF_MAP_NAME, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
            }
        )

        description = "Add a new floor. "
        if not self.floors_data:
            description += "Existing auto-calculated trim values will be used for this first floor."
        else:
            description += (
                "Trim values will be auto-calculated when you use 'Save Map Trims'."
            )

        return self.async_show_form(
            step_id="add_floor",
            data_schema=schema,
            description_placeholders={"info": description},
        )

    async def async_step_edit_floor(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Edit map name for an existing floor."""
        if user_input is not None:
            if self.selected_floor is None:
                # First step: select which floor to edit
                self.selected_floor = user_input.get(CONF_FLOOR_NAME)
                return await self.async_step_edit_floor()

            # Second step: update only the map_name (trims are auto-calculated)
            map_name = user_input.get(CONF_MAP_NAME, "")

            # Keep existing trims data
            floor_data = self.floors_data.get(self.selected_floor, {})
            existing_trims = floor_data.get("trims", {})

            updated_floor = FloorData(
                trims=TrimsData(
                    floor=self.selected_floor,
                    trim_up=existing_trims.get("trim_up", 0),
                    trim_down=existing_trims.get("trim_down", 0),
                    trim_left=existing_trims.get("trim_left", 0),
                    trim_right=existing_trims.get("trim_right", 0),
                ),
                map_name=map_name,
            )

            updated_floors = dict(self.floors_data)
            updated_floors[self.selected_floor] = updated_floor.to_dict()

            self.camera_options = {
                CONF_FLOORS_DATA: updated_floors,
            }
            floor_name = self.selected_floor
            self.selected_floor = None
            LOGGER.info("Updated floor: %s", floor_name)
            return await self.async_step_floor_management()

        # First step: select floor to edit
        if self.selected_floor is None:
            floor_options = list(self.floors_data.keys()) if self.floors_data else []

            if not floor_options:
                LOGGER.warning("No floors available to edit")
                return self.async_abort(reason="no_floors")

            schema = vol.Schema(
                {
                    vol.Required(CONF_FLOOR_NAME): SelectSelector(
                        SelectSelectorConfig(
                            options=floor_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            )

            return self.async_show_form(
                step_id="edit_floor",
                data_schema=schema,
            )

        # Second step: edit the selected floor (only map_name, trims are read-only)
        floor_data = self.floors_data.get(self.selected_floor, {})
        trims_data = floor_data.get("trims", {})

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_MAP_NAME, default=floor_data.get("map_name", "")
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            }
        )

        # Show current trim values in description
        trim_info = (
            f"Current auto-calculated trims: "
            f"Top={trims_data.get('trim_up', 0)}, "
            f"Bottom={trims_data.get('trim_down', 0)}, "
            f"Left={trims_data.get('trim_left', 0)}, "
            f"Right={trims_data.get('trim_right', 0)}"
        )

        return self.async_show_form(
            step_id="edit_floor",
            data_schema=schema,
            description_placeholders={
                "floor_name": self.selected_floor,
                "trim_info": trim_info,
            },
        )

    async def async_step_delete_floor(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Delete a floor from the configuration."""
        if user_input is not None:
            floor_to_delete = user_input.get(CONF_FLOOR_NAME)

            updated_floors = dict(self.floors_data)
            if floor_to_delete in updated_floors:
                del updated_floors[floor_to_delete]

                # If we deleted the current floor, reset to floor_0
                new_current_floor = self.current_floor
                if floor_to_delete == self.current_floor:
                    new_current_floor = "floor_0"

                self.camera_options = {
                    CONF_FLOORS_DATA: updated_floors,
                    CONF_CURRENT_FLOOR: new_current_floor,
                }
                LOGGER.info("Deleted floor: %s", floor_to_delete)
                return await self.async_step_floor_management()

        floor_options = list(self.floors_data.keys()) if self.floors_data else []

        if not floor_options:
            LOGGER.warning("No floors available to delete")
            return self.async_abort(reason="no_floors")

        schema = vol.Schema(
            {
                vol.Required(CONF_FLOOR_NAME): SelectSelector(
                    SelectSelectorConfig(
                        options=floor_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="delete_floor",
            data_schema=schema,
        )

    async def async_step_save_options(self, user_input=None):
        """
        Save the options in a sorted way. It stores all the options.
        """
        LOGGER.debug(
            "Storing Updated Camera (%s) Options.", self.camera_config.unique_id
        )
        try:
            opt_update = await update_options(self.backup_options, self.camera_options)
            LOGGER.debug("updated options:%s", dict(opt_update))
            return self.async_create_entry(
                title="",
                data=opt_update,
            )
        except ConfigEntryError as e:
            LOGGER.error(
                "Configuration error while storing options: %s", e, exc_info=True
            )
            return self.async_abort(reason="config_error")
        except ConfigEntryNotReady as e:
            LOGGER.error("System not ready while storing options: %s", e, exc_info=True)
            return self.async_abort(reason="not_ready")

"""Options flow schema definitions using dataclasses."""

from dataclasses import dataclass
from typing import Any

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    BooleanSelector,
    ColorRGBSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import voluptuous as vol

from ...const import (
    ALLOWED_IMAGE_FORMAT,
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
    CONF_MAP_NAME,
    CONF_MOP_PATH_WIDTH,
    CONF_OBSTACLE_LINK_IP,
    CONF_OBSTACLE_LINK_PORT,
    CONF_OBSTACLE_LINK_PROTOCOL,
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
    DRAW_FLAGS,
    FONTS_AVAILABLE,
    IS_ALPHA,
    IS_ALPHA_R1,
    PROTOCOL_VALUES,
    RATIO_VALUES,
    ROBOT_SIZE_VALUES,
    ROOM_FLAGS,
    ROTATION_VALUES,
    TEXT_SIZE_VALUES,
)


@dataclass
class OptionsSchemas:
    """Container for all options flow schemas."""

    config_entry: Any
    is_alpha_enabled: bool

    def __post_init__(self):
        """Initialize schemas after dataclass initialization."""
        # Selector configurations
        self.config_dict: NumberSelectorConfig = ALPHA_VALUES
        self.config_size: NumberSelectorConfig = TEXT_SIZE_VALUES
        self.robot_size_selector: NumberSelectorConfig = ROBOT_SIZE_VALUES
        self.mop_path_selector: NumberSelectorConfig = {
            "min": 1,
            "max": 50,
            "step": 1,
            "mode": NumberSelectorMode.BOX,
        }
        self.font_selector = SelectSelectorConfig(
            options=FONTS_AVAILABLE,
            mode=SelectSelectorMode.DROPDOWN,
        )
        self.rotation_selector = SelectSelectorConfig(
            options=ROTATION_VALUES,
            mode=SelectSelectorMode.DROPDOWN,
        )
        self.aspect_ratio_selector = SelectSelectorConfig(
            options=RATIO_VALUES,
            mode=SelectSelectorMode.DROPDOWN,
        )
        self.image_format_selector = SelectSelectorConfig(
            options=list(ALLOWED_IMAGE_FORMAT.keys()),
            mode=SelectSelectorMode.DROPDOWN,
        )

    @property
    def image_schema(self) -> vol.Schema:
        """Return image configuration schema."""
        return vol.Schema(
            {
                vol.Required(
                    ATTR_ROTATE, default=self.config_entry.options.get("rotate_image")
                ): SelectSelector(self.rotation_selector),
                vol.Optional(
                    ATTR_MARGINS, default=self.config_entry.options.get("margins")
                ): cv.string,
                vol.Required(
                    CONF_ASPECT_RATIO,
                    default=self.config_entry.options.get("aspect_ratio"),
                ): SelectSelector(self.aspect_ratio_selector),
                vol.Optional(
                    CONF_ZOOM_LOCK_RATIO,
                    default=self.config_entry.options.get("zoom_lock_ratio"),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_AUTO_ZOOM,
                    default=self.config_entry.options.get("auto_zoom"),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_ROBOT_SIZE,
                    default=self.config_entry.options.get("robot_size"),
                ): NumberSelector(self.robot_size_selector),
                vol.Optional(
                    CONF_MOP_PATH_WIDTH,
                    default=self.config_entry.options.get("mop_path_width", 10),
                ): NumberSelector(self.mop_path_selector),
                vol.Required(
                    CONF_DEF_CONTEXT_TYPE,
                    default=self.config_entry.options.get("def_context_type", "jpeg"),
                ): SelectSelector(self.image_format_selector),
            }
        )

    @property
    def image_schema_2(self) -> vol.Schema:
        """Return image offset configuration schema."""
        return vol.Schema(
            {
                vol.Optional(
                    CONF_OFFSET_TOP, default=self.config_entry.options.get("offset_top")
                ): cv.positive_int,
                vol.Optional(
                    CONF_OFFSET_BOTTOM,
                    default=self.config_entry.options.get("offset_bottom"),
                ): cv.positive_int,
                vol.Optional(
                    CONF_OFFSET_LEFT,
                    default=self.config_entry.options.get("offset_left"),
                ): cv.positive_int,
                vol.Optional(
                    CONF_OFFSET_RIGHT,
                    default=self.config_entry.options.get("offset_right"),
                ): cv.positive_int,
            }
        )

    @property
    def status_text_options(self) -> vol.Schema:
        """Return status text configuration schema."""
        return vol.Schema(
            {
                vol.Optional(
                    CONF_VAC_STAT,
                    default=self.config_entry.options.get("show_vac_status"),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_VAC_STAT_FONT,
                    default=self.config_entry.options.get("vac_status_font"),
                ): SelectSelector(self.font_selector),
                vol.Optional(
                    CONF_VAC_STAT_SIZE,
                    default=self.config_entry.options.get("vac_status_size"),
                ): NumberSelector(self.config_size),
                vol.Optional(
                    CONF_VAC_STAT_POS,
                    default=self.config_entry.options.get("vac_status_position"),
                ): BooleanSelector(),
                vol.Optional(
                    COLOR_TEXT, default=self.config_entry.options.get("color_text")
                ): ColorRGBSelector(),
            }
        )

    @property
    def colors_base_schema(self) -> vol.Schema:
        """Return base colors configuration schema."""
        return vol.Schema(
            {
                vol.Optional(
                    COLOR_BACKGROUND,
                    default=self.config_entry.options.get("color_background"),
                ): ColorRGBSelector(),
                vol.Optional(
                    COLOR_ZONE_CLEAN,
                    default=self.config_entry.options.get("color_zone_clean"),
                ): ColorRGBSelector(),
                vol.Optional(
                    COLOR_WALL, default=self.config_entry.options.get("color_wall")
                ): ColorRGBSelector(),
                vol.Optional(
                    COLOR_ROBOT, default=self.config_entry.options.get("color_robot")
                ): ColorRGBSelector(),
                vol.Optional(
                    COLOR_CHARGER,
                    default=self.config_entry.options.get("color_charger"),
                ): ColorRGBSelector(),
                vol.Optional(
                    COLOR_MOVE, default=self.config_entry.options.get("color_move")
                ): ColorRGBSelector(),
                vol.Optional(
                    COLOR_MOP_MOVE,
                    default=self.config_entry.options.get("color_mop_move"),
                ): ColorRGBSelector(),
                vol.Optional(
                    COLOR_GO_TO, default=self.config_entry.options.get("color_go_to")
                ): ColorRGBSelector(),
                vol.Optional(
                    COLOR_NO_GO, default=self.config_entry.options.get("color_no_go")
                ): ColorRGBSelector(),
                vol.Optional(
                    IS_ALPHA, default=self.is_alpha_enabled
                ): BooleanSelector(),
            }
        )

    @property
    def colors_alpha_1_schema(self) -> vol.Schema:
        """Return alpha values configuration schema."""
        return vol.Schema(
            {
                vol.Optional(
                    ALPHA_BACKGROUND,
                    default=self.config_entry.options.get("alpha_background"),
                ): NumberSelector(self.config_dict),
                vol.Optional(
                    ALPHA_ZONE_CLEAN,
                    default=self.config_entry.options.get("alpha_zone_clean"),
                ): NumberSelector(self.config_dict),
                vol.Optional(
                    ALPHA_WALL, default=self.config_entry.options.get("alpha_wall")
                ): NumberSelector(self.config_dict),
                vol.Optional(
                    ALPHA_ROBOT, default=self.config_entry.options.get("alpha_robot")
                ): NumberSelector(self.config_dict),
                vol.Optional(
                    ALPHA_CHARGER,
                    default=self.config_entry.options.get("alpha_charger"),
                ): NumberSelector(self.config_dict),
                vol.Optional(
                    ALPHA_MOVE, default=self.config_entry.options.get("alpha_move")
                ): NumberSelector(self.config_dict),
                vol.Optional(
                    ALPHA_MOP_MOVE,
                    default=self.config_entry.options.get("alpha_mop_move"),
                ): NumberSelector(self.config_dict),
                vol.Optional(
                    ALPHA_GO_TO, default=self.config_entry.options.get("alpha_go_to")
                ): NumberSelector(self.config_dict),
                vol.Optional(
                    ALPHA_NO_GO, default=self.config_entry.options.get("alpha_no_go")
                ): NumberSelector(self.config_dict),
                vol.Optional(
                    ALPHA_TEXT, default=self.config_entry.options.get("alpha_text")
                ): NumberSelector(self.config_dict),
            }
        )

    @property
    def materials_schema(self) -> vol.Schema:
        """Return materials configuration schema."""
        return vol.Schema(
            {
                vol.Optional(
                    CONF_DISABLE_MATERIAL_OVERLAY,
                    default=self.config_entry.options.get(
                        "disable_material_overlay", False
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_DISABLE_CARPETS,
                    default=self.config_entry.options.get("disable_carpets", False),
                ): BooleanSelector(),
                vol.Optional(
                    COLOR_CARPET,
                    default=self.config_entry.options.get("color_carpet"),
                ): ColorRGBSelector(),
                vol.Optional(
                    COLOR_MATERIAL_WOOD,
                    default=self.config_entry.options.get("color_material_wood"),
                ): ColorRGBSelector(),
                vol.Optional(
                    COLOR_MATERIAL_TILE,
                    default=self.config_entry.options.get("color_material_tile"),
                ): ColorRGBSelector(),
                vol.Optional(
                    ALPHA_CARPET,
                    default=self.config_entry.options.get("alpha_carpet"),
                ): NumberSelector(self.config_dict),
                vol.Optional(
                    ALPHA_MATERIAL_WOOD,
                    default=self.config_entry.options.get("alpha_material_wood"),
                ): NumberSelector(self.config_dict),
                vol.Optional(
                    ALPHA_MATERIAL_TILE,
                    default=self.config_entry.options.get("alpha_material_tile"),
                ): NumberSelector(self.config_dict),
            }
        )

    def obstacle_link_schema(self, vacuum_ip: str = "") -> vol.Schema:
        """Return obstacle link configuration schema.

        Args:
            vacuum_ip: Default vacuum IP address to pre-populate the field

        Returns:
            vol.Schema with obstacle link configuration fields
        """
        # Get current IP from options, fallback to vacuum_ip, then empty string
        default_ip = self.config_entry.options.get(CONF_OBSTACLE_LINK_IP)
        if not default_ip:
            default_ip = vacuum_ip

        return vol.Schema(
            {
                vol.Optional(
                    CONF_OBSTACLE_LINK_PROTOCOL,
                    default=self.config_entry.options.get(
                        CONF_OBSTACLE_LINK_PROTOCOL, "http"
                    ),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=PROTOCOL_VALUES,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_OBSTACLE_LINK_PORT,
                    default=self.config_entry.options.get(CONF_OBSTACLE_LINK_PORT, 80),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=65535,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_OBSTACLE_LINK_IP,
                    default=default_ip,
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            }
        )

    def build_boolean_fields_schema(self, flags: list, limit: int = None) -> vol.Schema:
        """Build a schema with boolean fields from a list of flags.

        Args:
            flags: List of flag constants to use for building fields
            limit: Optional limit on the number of flags to use (for rooms)

        Returns:
            vol.Schema with boolean fields
        """
        fields = {}
        flags_to_use = flags[:limit] if limit is not None else flags

        for flag in flags_to_use:
            fields[
                vol.Optional(
                    flag,
                    default=self.config_entry.options.get(flag, False),
                )
            ] = BooleanSelector()

        return vol.Schema(fields)

    @property
    def map_elements_schema(self) -> vol.Schema:
        """Return map elements visibility schema."""
        return self.build_boolean_fields_schema(DRAW_FLAGS)

    def segments_visibility_schema(self, room_limit: int) -> vol.Schema:
        """Return segments visibility schema with dynamic room limit.

        Args:
            room_limit: Maximum number of rooms to show

        Returns:
            vol.Schema with room visibility fields
        """
        return self.build_boolean_fields_schema(ROOM_FLAGS, room_limit)

    def floor_only_schema(self, is_alpha_enabled: bool) -> vol.Schema:
        """Return floor-only color schema (single room).

        Args:
            is_alpha_enabled: Whether alpha configuration is enabled

        Returns:
            vol.Schema with single room color field
        """
        return vol.Schema(
            {
                vol.Optional(
                    COLOR_ROOM_0,
                    default=self.config_entry.options.get("color_room_0"),
                ): ColorRGBSelector(),
                vol.Optional(IS_ALPHA_R1, default=is_alpha_enabled): BooleanSelector(),
            }
        )

    def rooms_colours_schema(
        self, start_room: int, end_room: int, is_alpha_enabled: bool, alpha_key: str
    ) -> vol.Schema:
        """Return dynamic rooms color schema.

        Args:
            start_room: Starting room index (inclusive)
            end_room: Ending room index (exclusive)
            is_alpha_enabled: Whether alpha configuration is enabled
            alpha_key: Alpha key constant (IS_ALPHA_R1 or IS_ALPHA_R2)

        Returns:
            vol.Schema with room color fields
        """
        fields = {}
        for i in range(start_room, end_room):
            fields[
                vol.Optional(
                    f"color_room_{i}",
                    default=self.config_entry.options.get(f"color_room_{i}"),
                )
            ] = ColorRGBSelector()

        fields[vol.Optional(alpha_key, default=is_alpha_enabled)] = BooleanSelector()
        return vol.Schema(fields)

    def alpha_floor_schema(self) -> vol.Schema:
        """Return floor-only alpha schema (single room).

        Returns:
            vol.Schema with single room alpha field
        """
        return vol.Schema(
            {
                vol.Optional(
                    ALPHA_ROOM_0,
                    default=self.config_entry.options.get("alpha_room_0"),
                ): NumberSelector(self.config_dict),
            }
        )

    def rooms_alpha_schema(self, start_room: int, end_room: int) -> vol.Schema:
        """Return dynamic rooms alpha schema.

        Args:
            start_room: Starting room index (inclusive)
            end_room: Ending room index (exclusive)

        Returns:
            vol.Schema with room alpha fields
        """
        fields = {}
        for i in range(start_room, end_room):
            fields[
                vol.Optional(
                    f"alpha_room_{i}",
                    default=self.config_entry.options.get(f"alpha_room_{i}"),
                )
            ] = NumberSelector(self.config_dict)

        return vol.Schema(fields)

    def select_floor_schema(
        self, floor_options: list, current_floor: str
    ) -> vol.Schema:
        """Return floor selection schema.

        Args:
            floor_options: List of dicts with 'label' and 'value' keys
            current_floor: Currently selected floor ID

        Returns:
            vol.Schema with floor selection dropdown
        """
        return vol.Schema(
            {
                vol.Required(CONF_CURRENT_FLOOR, default=current_floor): SelectSelector(
                    SelectSelectorConfig(
                        options=floor_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

    def add_floor_schema(
        self, available_floors: list, include_trims: bool
    ) -> vol.Schema:
        """Return add floor schema with optional trim fields.

        Args:
            available_floors: List of dicts with 'label' and 'value' keys
            include_trims: Whether to include trim fields (False for first floor)

        Returns:
            vol.Schema with floor name, map name, and optional trim fields
        """
        # Determine floor selector based on available floors
        if available_floors:
            floor_selector = SelectSelector(
                SelectSelectorConfig(
                    options=available_floors,
                    mode=SelectSelectorMode.DROPDOWN,
                    custom_value=True,
                )
            )
        else:
            floor_selector = TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            )

        schema_fields = {
            vol.Required(CONF_FLOOR_NAME): floor_selector,
            vol.Optional(CONF_MAP_NAME, default=""): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
        }

        # Add trim fields if this is NOT the first floor
        if include_trims:
            schema_fields.update(
                {
                    vol.Optional(CONF_TRIM_UP, default=0): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=8000, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(CONF_TRIM_LEFT, default=0): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=8000, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(CONF_TRIM_DOWN, default=0): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=8000, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(CONF_TRIM_RIGHT, default=0): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=8000, mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            )

        return vol.Schema(schema_fields)

    def edit_floor_select_schema(self, floor_options: list) -> vol.Schema:
        """Return floor selection schema for editing.

        Args:
            floor_options: List of dicts with 'label' and 'value' keys

        Returns:
            vol.Schema with floor selection dropdown
        """
        return vol.Schema(
            {
                vol.Required(CONF_FLOOR_NAME): SelectSelector(
                    SelectSelectorConfig(
                        options=floor_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

    def edit_floor_data_schema(self, floor_data: dict) -> vol.Schema:
        """Return floor data editing schema with map name and trim fields.

        Args:
            floor_data: Floor data dict containing map_name and trims

        Returns:
            vol.Schema with map name and trim fields
        """
        trims_data = floor_data.get("trims", {})

        return vol.Schema(
            {
                vol.Optional(
                    CONF_MAP_NAME, default=floor_data.get("map_name", "")
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Optional(
                    CONF_TRIM_UP, default=trims_data.get("trim_up", 0)
                ): NumberSelector(
                    NumberSelectorConfig(min=0, max=8000, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(
                    CONF_TRIM_LEFT, default=trims_data.get("trim_left", 0)
                ): NumberSelector(
                    NumberSelectorConfig(min=0, max=8000, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(
                    CONF_TRIM_DOWN, default=trims_data.get("trim_down", 0)
                ): NumberSelector(
                    NumberSelectorConfig(min=0, max=8000, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(
                    CONF_TRIM_RIGHT, default=trims_data.get("trim_right", 0)
                ): NumberSelector(
                    NumberSelectorConfig(min=0, max=8000, mode=NumberSelectorMode.BOX)
                ),
            }
        )

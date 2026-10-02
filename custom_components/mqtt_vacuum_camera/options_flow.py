"""
Options flow handler for MQTT Vacuum Camera integration.
Last Updated on version: 2026.2.0
"""

from copy import deepcopy
from typing import Any, Dict, Optional

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import floor_registry as fr
from valetudo_map_parser.config.types import RoomStore

from .common import extract_file_name, update_options
from .const import (
    CONF_CURRENT_FLOOR,
    CONF_FLOOR_NAME,
    CONF_FLOORS_DATA,
    CONF_MAP_NAME,
    DEFAULT_ROOMS,
    DEFAULT_ROOMS_NAMES,
    DOMAIN,
    DRAW_FLAGS,
    IS_ALPHA,
    IS_ALPHA_R1,
    IS_ALPHA_R2,
    LOGGER,
    ROOM_FLAGS,
)
from .utils.options import OptionsSchemas, floor_helpers
from .utils.options.option_fields import (
    BASE_ALPHA_FIELDS,
    BASE_COLOURS_FIELDS,
    FLOOR_ALPHA_FIELDS,
    FLOOR_COLOUR_FIELDS,
    IMAGE_BASIC_FIELDS,
    MATERIALS_FIELDS,
    OBSTACLE_LINK_FIELDS,
    STATUS_TEXT_FIELDS,
    extract_options,
    room_fields,
    same_key_fields,
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
        self.camera_options: dict[str, Any] = {}
        self.backup_options = deepcopy(dict(self.camera_config.options))
        self.file_name = extract_file_name(self.unique_id or "")
        self.is_alpha_enabled = False
        self.number_of_rooms = DEFAULT_ROOMS
        self.rooms_placeholders = DEFAULT_ROOMS_NAMES
        self.floors_data = dict(self.camera_config.options.get("floors_data", {}))
        self.current_floor = self.camera_config.options.get("current_floor", "floor_0")
        self.selected_floor: Optional[str] = None
        # Initialize schemas using dataclass
        self._schemas = OptionsSchemas(
            config_entry=config_entry, is_alpha_enabled=self.is_alpha_enabled
        )

    def _get_ha_floors(self) -> list[dict[str, str]]:
        """Get list of floors with both ID and display name.

        Returns:
            List of dicts with 'floor_id' and 'name' keys
        """
        try:
            floor_reg = fr.async_get(self.hass)
            floors = list(floor_reg.async_list_floors())
            return (
                [{"floor_id": floor.floor_id, "name": floor.name} for floor in floors]
                if floors
                else []
            )
        except (AttributeError, ValueError, KeyError) as e:
            LOGGER.warning("Failed to get HA floors: %s", e)
            return []

    def _get_floor_dropdown_options(
        self, filter_configured: bool = False, use_configured: bool = False
    ) -> list[dict[str, str]]:
        """Get floor options for dropdowns with display names.

        Args:
            filter_configured: If True, exclude already configured floors (for add_floor)
            use_configured: If True, use floors_data keys instead of HA floors (for edit/delete)

        Returns:
            List of dicts with 'label' and 'value' keys for SelectSelector
        """
        return floor_helpers.floor_dropdown_options(
            self._get_ha_floors(),
            self.floors_data,
            filter_configured=filter_configured,
            use_configured=use_configured,
        )

    def _first_rooms_group_count(self) -> int:
        """Number of rooms shown in the first colour / alpha step (max 8)."""
        if self.number_of_rooms > 8:
            return 8
        if self.number_of_rooms != 0:
            return self.number_of_rooms
        return 1

    async def async_step_init(
        self,
        user_input=None,  # pylint: disable=unused-argument
    ) -> ConfigFlowResult:
        """Start the options menu configuration."""
        rooms_data = RoomStore(self.file_name)
        self.number_of_rooms = rooms_data.get_rooms_count()
        self.rooms_placeholders = (
            rooms_data.room_names if rooms_data.room_names else DEFAULT_ROOMS_NAMES
        )
        if (
            not isinstance(self.number_of_rooms, int)
            or self.number_of_rooms < DEFAULT_ROOMS
        ):
            LOGGER.error("No rooms found in the configuration. Aborting.")
            return self.async_abort(reason="no_rooms")

        return self.async_show_menu(
            step_id="init",
            menu_options=["image_opt", "colours", "materials", "save_options"],
        )

    async def async_step_main_menu(
        self,
        user_input=None,  # pylint: disable=unused-argument
    ) -> ConfigFlowResult:
        """Return to main menu."""
        return await self.async_step_init()

    async def async_step_image_opt(
        self,
        user_input=None,  # pylint: disable=unused-argument
    ) -> ConfigFlowResult:
        """Handle image options menu."""
        return self.async_show_menu(
            step_id="image_opt",
            menu_options=[
                "image_basic_opt",
                "status_text",
                "draw_elements",
                "floor_management",
                "obstacle_link_config",
                "main_menu",
            ],
        )

    async def async_step_draw_elements(
        self,
        user_input=None,  # pylint: disable=unused-argument
    ) -> ConfigFlowResult:
        """Handle draw elements menu."""
        return self.async_show_menu(
            step_id="draw_elements",
            menu_options=[
                "map_elements",
                "segments_visibility",
                "main_menu",
            ],
        )

    async def async_step_colours(
        self,
        user_input=None,  # pylint: disable=unused-argument
    ) -> ConfigFlowResult:
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

    async def async_step_transparency(
        self,
        user_input=None,  # pylint: disable=unused-argument
    ) -> ConfigFlowResult:
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
            self.camera_options.update(extract_options(user_input, MATERIALS_FIELDS))
            return await self.async_step_init()

        return self.async_show_form(
            step_id="materials",
            data_schema=self._schemas.materials_schema,
        )

    # Image Settings Steps
    async def async_step_image_basic_opt(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """Handle basic image settings."""
        if user_input is not None:
            self.camera_options.update(extract_options(user_input, IMAGE_BASIC_FIELDS))
            return await self.async_step_image_opt()

        return self.async_show_form(
            step_id="image_basic_opt",
            data_schema=self._schemas.image_schema,
        )

    async def async_step_floor_management(
        self,
        user_input=None,  # pylint: disable=unused-argument
    ) -> ConfigFlowResult:
        """Handle floor management menu."""
        return self.async_show_menu(
            step_id="floor_management",
            menu_options=[
                "select_floor",
                "add_floor",
                "edit_floor",
                "delete_floor",
                "update_floor_data",
                "main_menu",
            ],
        )

    async def async_step_status_text(self, user_input: Optional[Dict[str, Any]] = None):
        """Handle status text settings."""
        if user_input is not None:
            self.camera_options.update(extract_options(user_input, STATUS_TEXT_FIELDS))
            return await self.async_step_image_opt()

        return self.async_show_form(
            step_id="status_text",
            data_schema=self._schemas.status_text_options,
        )

    async def async_step_obstacle_link_config(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Handle obstacle image link configuration."""
        if user_input is not None:
            self.camera_options.update(
                extract_options(user_input, OBSTACLE_LINK_FIELDS)
            )
            return await self.async_step_image_opt()

        # Get vacuum IP from coordinator to use as default
        vacuum_ip = ""
        try:
            hass_data = self.hass.data.get(DOMAIN, {}).get(self.camera_config.entry_id)
            if hass_data and "coordinator" in hass_data:
                coordinator = hass_data["coordinator"]
                if hasattr(coordinator, "context") and hasattr(
                    coordinator.context, "shared"
                ):
                    vacuum_ip = coordinator.context.shared.vacuum_ips or ""
        except (AttributeError, KeyError):
            # If we can't get the vacuum IP, use empty string
            pass

        return self.async_show_form(
            step_id="obstacle_link_config",
            data_schema=self._schemas.obstacle_link_schema(vacuum_ip),
        )

    async def async_step_map_elements(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """Handle map elements visibility configuration."""
        if user_input is not None:
            # Update options based on user input using DRAW_FLAGS
            self.camera_options.update(
                extract_options(user_input, same_key_fields(DRAW_FLAGS), default=False)
            )
            return await self.async_step_draw_elements()

        return self.async_show_form(
            step_id="map_elements",
            data_schema=self._schemas.map_elements_schema,
        )

    async def async_step_segments_visibility(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """Handle segments (rooms) visibility configuration."""

        # Limit to the number of rooms that exist
        room_limit = min(self.number_of_rooms, 15)

        if user_input is not None:
            # Update options based on user input using ROOM_FLAGS
            self.camera_options.update(
                extract_options(
                    user_input,
                    same_key_fields(ROOM_FLAGS[:room_limit]),
                    default=False,
                )
            )
            return await self.async_step_draw_elements()

        return self.async_show_form(
            step_id="segments_visibility",
            data_schema=self._schemas.segments_visibility_schema(room_limit),
            description_placeholders=self.rooms_placeholders,
        )

    async def async_step_base_colours(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """Base Colours Configuration."""
        if user_input is not None:
            self.camera_options.update(extract_options(user_input, BASE_COLOURS_FIELDS))
            self.is_alpha_enabled = bool(user_input.get(IS_ALPHA))
            if self.is_alpha_enabled:
                self.is_alpha_enabled = False
                return await self.async_step_alpha_1()
            return await self.async_step_colours()

        return self.async_show_form(
            step_id="base_colours",
            data_schema=self._schemas.colors_base_schema,
        )

    async def async_step_alpha_1(self, user_input: Optional[Dict[str, Any]] = None):
        """Transparency Configuration for the Base Colours."""
        if user_input is not None:
            self.camera_options.update(extract_options(user_input, BASE_ALPHA_FIELDS))
            return await self.async_step_transparency()

        return self.async_show_form(
            step_id="alpha_1",
            data_schema=self._schemas.colors_alpha_1_schema,
        )

    async def async_step_floor_only(self, user_input: Optional[Dict[str, Any]] = None):
        """Floor colours configuration step based on one room only."""
        if user_input is not None:
            # Update options based on user input
            self.camera_options.update(extract_options(user_input, FLOOR_COLOUR_FIELDS))
            self.is_alpha_enabled = user_input.get(IS_ALPHA_R1, False)
            if self.is_alpha_enabled:
                return await self.async_step_alpha_floor()
            return await self.async_step_colours()

        return self.async_show_form(
            step_id="floor_only",
            data_schema=self._schemas.floor_only_schema(self.is_alpha_enabled),
        )

    async def async_step_rooms_colours_1(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """Dynamically generate rooms colours configuration step based on the number of rooms."""
        rooms_count = self._first_rooms_group_count()

        if user_input is not None:
            # Update options based on user input
            self.camera_options.update(
                extract_options(user_input, room_fields("color_room", 0, rooms_count))
            )
            self.is_alpha_enabled = user_input.get(IS_ALPHA_R1, False)

            if self.is_alpha_enabled:
                return await self.async_step_alpha_2()
            return await self.async_step_colours()

        return self.async_show_form(
            step_id="rooms_colours_1",
            data_schema=self._schemas.rooms_colours_schema(
                0, rooms_count, self.is_alpha_enabled, IS_ALPHA_R1
            ),
            description_placeholders=self.rooms_placeholders,
        )

    async def async_step_rooms_colours_2(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """Dynamically generate rooms colours configuration step based on the number of rooms."""
        end_room = min(self.number_of_rooms, 16)

        if user_input is not None:
            # Update options based on user input
            self.camera_options.update(
                extract_options(user_input, room_fields("color_room", 8, end_room))
            )
            self.is_alpha_enabled = user_input.get(IS_ALPHA_R2, False)

            if self.is_alpha_enabled:
                return await self.async_step_alpha_3()
            return await self.async_step_colours()

        return self.async_show_form(
            step_id="rooms_colours_2",
            data_schema=self._schemas.rooms_colours_schema(
                8, end_room, self.is_alpha_enabled, IS_ALPHA_R2
            ),
            description_placeholders=self.rooms_placeholders,
        )

    async def async_step_alpha_floor(self, user_input: Optional[Dict[str, Any]] = None):
        """Floor alpha configuration step based on one room only."""
        if user_input is not None:
            # Update options based on user input
            self.camera_options.update(extract_options(user_input, FLOOR_ALPHA_FIELDS))
            return await self.async_step_transparency()

        return self.async_show_form(
            step_id="alpha_floor",
            data_schema=self._schemas.alpha_floor_schema(),
        )

    async def async_step_alpha_2(self, user_input: Optional[Dict[str, Any]] = None):
        """Dynamically generate rooms colours configuration step based on the number of rooms."""
        rooms_count = self._first_rooms_group_count()

        if user_input is not None:
            # Update options based on user input
            self.camera_options.update(
                extract_options(user_input, room_fields("alpha_room", 0, rooms_count))
            )
            return await self.async_step_transparency()

        return self.async_show_form(
            step_id="alpha_2",
            data_schema=self._schemas.rooms_alpha_schema(0, rooms_count),
            description_placeholders=self.rooms_placeholders,
        )

    async def async_step_alpha_3(self, user_input: Optional[Dict[str, Any]] = None):
        """Dynamically generate rooms colours configuration step based on the number of rooms."""
        end_room = min(self.number_of_rooms, 16)

        if user_input is not None:
            # Update options based on user input
            self.camera_options.update(
                extract_options(user_input, room_fields("alpha_room", 8, end_room))
            )
            return await self.async_step_transparency()

        return self.async_show_form(
            step_id="alpha_3",
            data_schema=self._schemas.rooms_alpha_schema(8, end_room),
            description_placeholders=self.rooms_placeholders,
        )

    # Floor Management Steps

    async def async_step_update_floor_data(
        self,
        user_input=None,  # pylint: disable=unused-argument
    ):
        """Update floor data with current trims."""
        entry = self.camera_config.entry_id
        coordinator = self.hass.data[DOMAIN][entry]["coordinator"]

        # If multi-floor is enabled, update the current floor's FloorData
        if self.floors_data and self.current_floor:
            # Current auto-calculated trims from coordinator.context.shared
            current_trims = coordinator.context.shared.trims.to_dict()

            # Get current rotation from camera options or config
            current_rotation = int(
                self.camera_options.get(
                    "rotate_image", self.camera_config.options.get("rotate_image", "0")
                )
            )

            self.floors_data, trims_data = floor_helpers.refresh_floor(
                self.floors_data, self.current_floor, current_trims, current_rotation
            )

            # Update trims_data (legacy single-floor support)
            self.camera_options.update(
                {
                    "trims_data": trims_data,
                    "floors_data": self.floors_data,
                    "current_floor": self.current_floor,
                }
            )

        return await self.async_step_edit_floor()

    async def async_step_select_floor(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Select the current active floor."""
        if user_input is not None:
            selected_floor_id = user_input.get(CONF_CURRENT_FLOOR)

            # Update instance variable
            self.current_floor = selected_floor_id

            # Update camera_options using .update() to preserve other options
            self.camera_options.update(
                {
                    CONF_CURRENT_FLOOR: selected_floor_id,
                }
            )
            return await self.async_step_floor_management()

        # Get floor options with display names
        floor_options = self._get_floor_dropdown_options()

        return self.async_show_form(
            step_id="select_floor",
            data_schema=self._schemas.select_floor_schema(
                floor_options, self.current_floor
            ),
            description_placeholders={"current_floor": self.current_floor},
        )

    async def async_step_add_floor(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Add a new floor with trim settings."""
        if user_input is not None:
            floor_id = str(user_input.get(CONF_FLOOR_NAME, ""))

            # Existing trims_data is the default for the first floor
            updated_floors = floor_helpers.add_floor(
                self.floors_data,
                floor_id,
                user_input.get(CONF_MAP_NAME, ""),
                user_input,
                self.camera_config.options.get("trims_data", {}),
            )

            # Update instance variables
            self.floors_data = updated_floors
            self.current_floor = floor_id

            # Update camera_options using .update()
            # to preserve other options
            self.camera_options.update(
                {
                    CONF_FLOORS_DATA: updated_floors,
                    CONF_CURRENT_FLOOR: floor_id,
                }
            )
            return await self.async_step_floor_management()

        # Get floor options with display names, filtered for available floors
        floor_options = self._get_floor_dropdown_options(filter_configured=True)

        return self.async_show_form(
            step_id="add_floor",
            data_schema=self._schemas.add_floor_schema(
                floor_options, bool(self.floors_data)
            ),
            description_placeholders={
                "info": floor_helpers.add_floor_description(bool(self.floors_data))
            },
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

            # Second step: update map_name and trim values
            updated_floors = floor_helpers.edit_floor(
                self.floors_data, self.selected_floor, user_input
            )

            # Update instance variables
            self.floors_data = updated_floors

            # Update camera_options using .update() to preserve other options
            self.camera_options.update(
                {
                    CONF_FLOORS_DATA: updated_floors,
                }
            )
            self.selected_floor = None
            return await self.async_step_floor_management()

        # First step: select floor to edit
        if self.selected_floor is None:
            if not self.floors_data:
                LOGGER.warning("No floors available to edit")
                return self.async_abort(reason="no_floors")

            # Get floor options from configured floors
            floor_options = self._get_floor_dropdown_options(use_configured=True)

            return self.async_show_form(
                step_id="edit_floor",
                data_schema=self._schemas.edit_floor_select_schema(floor_options),
                description_placeholders={
                    "floor_name": "",
                    "trim_info": "",
                },
            )

        # Second step: edit the selected floor (map_name and trim values)
        floor_data = self.floors_data.get(self.selected_floor, {})

        return self.async_show_form(
            step_id="edit_floor",
            data_schema=self._schemas.edit_floor_data_schema(floor_data),
            description_placeholders={
                "floor_name": self.selected_floor,
                "trim_info": floor_helpers.trim_info(floor_data),
            },
        )

    async def async_step_delete_floor(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Delete a floor from the configuration."""
        if user_input is not None:
            floor_to_delete = user_input.get(CONF_FLOOR_NAME)

            if floor_to_delete in self.floors_data:
                updated_floors, new_current_floor = floor_helpers.delete_floor(
                    self.floors_data,
                    floor_to_delete,
                    self.current_floor,
                    self._get_ha_floors(),
                )

                # Update instance variables
                self.floors_data = updated_floors
                self.current_floor = new_current_floor

                # Update camera_options using .update() to preserve other options
                self.camera_options.update(
                    {
                        CONF_FLOORS_DATA: updated_floors,
                        CONF_CURRENT_FLOOR: new_current_floor,
                    }
                )
                return await self.async_step_floor_management()

        if not self.floors_data:
            LOGGER.warning("No floors available to delete")
            return self.async_abort(reason="no_floors")

        # Get floor options from configured floors
        floor_options = self._get_floor_dropdown_options(use_configured=True)

        return self.async_show_form(
            step_id="delete_floor",
            data_schema=self._schemas.edit_floor_select_schema(floor_options),
        )

    async def async_step_save_options(
        self,
        user_input=None,  # pylint: disable=unused-argument
    ):
        """Save the options in a sorted way. It stores all the options."""
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

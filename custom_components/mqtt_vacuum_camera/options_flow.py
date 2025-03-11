"""
Options flow handler for MQTT Vacuum Camera integration.
Version: 2025.3.0b1
"""

from copy import deepcopy
from typing import Any, Dict, Optional

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    BooleanSelector,
    ColorRGBSelector,
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from valetudo_map_parser.config.types import RoomStore
import voluptuous as vol

from .common import extract_file_name, get_vacuum_device_info, update_options
from .const import (
    ALPHA_BACKGROUND,
    ALPHA_CHARGER,
    ALPHA_GO_TO,
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
    COLOR_CHARGER,
    COLOR_GO_TO,
    COLOR_MOVE,
    COLOR_NO_GO,
    COLOR_ROBOT,
    COLOR_ROOM_0,
    COLOR_TEXT,
    COLOR_WALL,
    COLOR_ZONE_CLEAN,
    CONF_ASPECT_RATIO,
    CONF_AUTO_ZOOM,
    CONF_OFFSET_BOTTOM,
    CONF_OFFSET_LEFT,
    CONF_OFFSET_RIGHT,
    CONF_OFFSET_TOP,
    CONF_SNAPSHOTS_ENABLE,
    CONF_VAC_STAT,
    CONF_VAC_STAT_FONT,
    CONF_VAC_STAT_POS,
    CONF_VAC_STAT_SIZE,
    CONF_VACUUM_CONFIG_ENTRY_ID,
    CONF_ZOOM_LOCK_RATIO,
    DEFAULT_ROOMS,
    DOMAIN,
    FONTS_AVAILABLE,
    IS_ALPHA,
    IS_ALPHA_R1,
    IS_ALPHA_R2,
    LOGGER,
    RATIO_VALUES,
    ROTATION_VALUES,
    TEXT_SIZE_VALUES,
)
from .snapshots.log_files import run_async_save_logs
from .utils.files_operations import async_del_file, async_rename_room_description


class MQTTCameraOptionsFlowHandler(OptionsFlow):
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
        LOGGER.debug(
            "Options edit in progress.. options before edit: %s", dict(self.backup_options)
        )
        options_values = list(self.camera_config.options.values())
        if len(options_values) > 0:
            self.config_dict: NumberSelectorConfig = ALPHA_VALUES
            config_size: NumberSelectorConfig = TEXT_SIZE_VALUES
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
                        CONF_AUTO_ZOOM,
                        default=config_entry.options.get("auto_zoom"),
                    ): BooleanSelector(),
                    vol.Optional(
                        CONF_ZOOM_LOCK_RATIO,
                        default=config_entry.options.get("zoom_lock_ratio"),
                    ): BooleanSelector(),
                    vol.Optional(
                        CONF_SNAPSHOTS_ENABLE,
                        default=config_entry.options.get(CONF_SNAPSHOTS_ENABLE, True),
                    ): BooleanSelector(),
                }
            )
            self.IMG_SCHEMA_2 = vol.Schema(
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
            self.TEXT_OPTIONS_SCHEMA = vol.Schema(
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
            self.COLOR_BASE_SCHEMA = vol.Schema(
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
            self.ALPHA_1_SCHEMA = vol.Schema(
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

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Start the options menu configuration."""
        LOGGER.info("%s: Options Configuration Started.", self.camera_config.unique_id)
        errors = {}

        rooms_data = RoomStore(self.file_name)
        self.number_of_rooms = rooms_data.get_rooms_count()
        LOGGER.debug("Rooms count: %s", self.number_of_rooms)
        if (
            not isinstance(self.number_of_rooms, int)
            or self.number_of_rooms < DEFAULT_ROOMS
        ):
            errors["base"] = "no_rooms"
            LOGGER.error("No rooms found in the configuration. Aborting.")
            return self.async_abort(reason="no_rooms")

        if self.number_of_rooms > 8:
            return self.async_show_menu(
                step_id="init",
                menu_options=[
                    "image_opt",
                    "base_colours",
                    "rooms_colours_1",
                    "rooms_colours_2",
                    "advanced",
                ],
            )
        elif self.number_of_rooms == 1:
            return self.async_show_menu(
                step_id="init",
                menu_options=["image_opt", "base_colours", "floor_only", "advanced"],
            )
        return self.async_show_menu(
            step_id="init",
            menu_options=["image_opt", "base_colours", "rooms_colours_1", "advanced"],
        )

    async def async_step_advanced(self, user_input=None):
        """Handle advanced options menu."""
        return self.async_show_menu(
            step_id="advanced",
            menu_options=[
                "image_offset",
                "status_text",
                "download_logs",
                "rename_translations",
                "reset_map_trims",
            ],
        )

    async def async_step_image_opt(self, user_input: Optional[Dict[str, Any]] = None):
        """
        Images Options Configuration
        """
        # "get_svg_file": user_input.get(CONF_EXPORT_SVG),
        if user_input is not None:
            self.camera_options.update(
                {
                    "rotate_image": user_input.get(ATTR_ROTATE),
                    "margins": user_input.get(ATTR_MARGINS),
                    "aspect_ratio": user_input.get(CONF_ASPECT_RATIO),
                    "auto_zoom": user_input.get(CONF_AUTO_ZOOM),
                    "zoom_lock_ratio": user_input.get(CONF_ZOOM_LOCK_RATIO),
                    "enable_www_snapshots": user_input.get(CONF_SNAPSHOTS_ENABLE),
                }
            )

            return await self.async_step_opt_save()

        return self.async_show_form(
            step_id="image_opt",
            data_schema=self.image_schema,
            description_placeholders=self.camera_options,
        )

    async def async_step_image_offset(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """
        Images Offset Configuration
        """
        if user_input is not None:
            self.camera_options.update(
                {
                    "offset_top": user_input.get(CONF_OFFSET_TOP),
                    "offset_bottom": user_input.get(CONF_OFFSET_BOTTOM),
                    "offset_left": user_input.get(CONF_OFFSET_LEFT),
                    "offset_right": user_input.get(CONF_OFFSET_RIGHT),
                }
            )

            return await self.async_step_opt_save()

        return self.async_show_form(
            step_id="image_offset",
            data_schema=self.IMG_SCHEMA_2,
            description_placeholders=self.camera_options,
        )

    async def async_step_status_text(self, user_input: Optional[Dict[str, Any]] = None):
        """
        Images Status Text Configuration
        """
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

            return await self.async_step_opt_save()

        return self.async_show_form(
            step_id="status_text",
            data_schema=self.TEXT_OPTIONS_SCHEMA,
            description_placeholders=self.camera_options,
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
            return await self.async_step_opt_save()

        return self.async_show_form(
            step_id="base_colours",
            data_schema=self.COLOR_BASE_SCHEMA,
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
            return await self.async_step_opt_save()

        return self.async_show_form(
            step_id="alpha_1",
            data_schema=self.ALPHA_1_SCHEMA,
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
            return await self.async_step_opt_save()

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
            return await self.async_step_opt_save()

        # Dynamically create data schema based on the number of rooms
        fields = {}
        for i in range(rooms_count):
            fields[
                vol.Optional(
                    f"color_room_{i}",
                    default=self.camera_config.options.get(f"color_room_{i}"),
                )
            ] = ColorRGBSelector()

        fields[vol.Optional(IS_ALPHA_R1, default=self.is_alpha_enabled)] = BooleanSelector()

        return self.async_show_form(
            step_id="rooms_colours_1",
            data_schema=vol.Schema(fields),
            description_placeholders=self.camera_options,
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
            return await self.async_step_opt_save()

        # Dynamically create data schema based on the number of rooms
        fields = {}
        for i in range(8, min(self.number_of_rooms, 16)):
            fields[
                vol.Optional(
                    f"color_room_{i}",
                    default=self.camera_config.options.get(f"color_room_{i}"),
                )
            ] = ColorRGBSelector()

        fields[vol.Optional(IS_ALPHA_R2, default=self.is_alpha_enabled)] = BooleanSelector()

        return self.async_show_form(
            step_id="rooms_colours_2",
            data_schema=vol.Schema(fields),
            description_placeholders=self.camera_options,
        )

    async def async_step_alpha_floor(self, user_input: Optional[Dict[str, Any]] = None):
        """Floor alpha configuration step based on one room only"""
        LOGGER.info("Floor Alpha Configuration Started.")

        if user_input is not None:
            # Update options based on user input
            self.camera_options.update({"alpha_room_0": user_input.get(ALPHA_ROOM_0)})
            return await self.async_step_opt_save()

        fields = {
            vol.Optional(
                ALPHA_ROOM_0, default=self.camera_config.options.get("alpha_room_0")
            ): NumberSelector(self.config_dict),
        }

        return self.async_show_form(
            step_id="alpha_floor",
            data_schema=vol.Schema(fields),
            description_placeholders=self.camera_options,
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

            return await self.async_step_opt_save()

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
            description_placeholders=self.camera_options,
        )

    async def async_step_alpha_3(self, user_input: Optional[Dict[str, Any]] = None):
        """Dynamically generate rooms colours configuration step based on the number of rooms."""
        LOGGER.info("Dynamic Rooms Alpha up to 16 Configuration Started.")
        if user_input is not None:
            # Update options based on user input
            for i in range(8, min(self.number_of_rooms, 16)):
                room_key = f"alpha_room_{i}"
                self.camera_options.update({room_key: user_input.get(room_key)})

            return await self.async_step_opt_save()

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
            description_placeholders=self.camera_options,
        )

    async def async_step_logs_move(self):
        """
        Move the logs from www config folder to .storage.
        """

        LOGGER.debug("Generating and Moving the logs.")
        await self.hass.async_create_task(
            run_async_save_logs(self.hass, self.file_name)
        )

        self.camera_options = self.backup_options
        return await self.async_step_opt_save()

    async def async_step_logs_remove(self):
        """
        Remove the logs from www config folder.
        """
        ha_dir = self.hass.config.path()
        destination_path = f"{ha_dir}/www/{self.file_name}.zip"
        await async_del_file(destination_path)
        self.camera_options = self.backup_options
        return await self.async_step_opt_save()

    async def async_step_download_logs(self, user_input=None):
        """
        Copy the logs from .storage to www config folder.
        """
        errors = {}
        if user_input is not None and "camera_logs_progres" in user_input:
            next_action = user_input["camera_logs_progres"]
            if next_action == "opt_1":
                return await self.async_step_logs_move()
            if next_action == "opt_2":
                return await self.async_step_logs_remove()
            if next_action == "no_action":
                ...  # do nothing
            else:
                errors["base"] = "incorrect_options_action"
        copy_options = SelectSelectorConfig(
            options=[
                {"label": "copy_the_logs_to_www", "value": "opt_1"},
                {"label": "delete_logs_from_www", "value": "opt_2"},
            ],
            translation_key="camera_logs_progres",
            mode=SelectSelectorMode.LIST,
        )
        data_schema = {"camera_logs_progres": SelectSelector(copy_options)}
        return self.async_show_form(
            step_id="download_logs",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_rename_translations(self, user_input=None):
        """
        Copy the logs from .storage to www config folder.
        """
        LOGGER.debug("Renaming the translations.")
        hass = self.hass
        if (user_input is None) and self.backup_options:
            if self.hass:
                await async_rename_room_description(hass, self.file_name)
                self.camera_options = self.backup_options
            return await self.async_step_opt_save()

        return self.async_show_form(step_id="rename_translations")

    async def async_step_reset_map_trims(self, user_input=None):
        """
        Update the map trims based on the camera configuration.

        If the stored trims (from camera_config.to_dict()) are all 0,
        then we update them with the current trims from the coordinator.
        Otherwise, we clear the trims (reset them to 0).
        """
        entry = self.camera_config.entry_id
        LOGGER.debug("Updating the map trims for %s", entry)

        # Retrieve the coordinator from hass.data
        coordinator = self.hass.data[DOMAIN][entry]["coordinator"]

        # Retrieve the stored trims from the camera_config
        config_options = self.camera_config.as_dict().get("options", {})
        config_trims = config_options.get("trims_data", {})
        LOGGER.debug("Current config trims_data: %s", config_trims)
        if (user_input is None) and self.backup_options:
            # Decide whether to update (store) or reset (clear) the trims
            if all(
                config_trims.get(key, 0) == 0
                for key in ("trim_down", "trim_left", "trim_right", "trim_up")
            ):
                # If all stored values are 0, then update them with the current trims.
                new_trims = coordinator.shared.trims.to_dict()
                LOGGER.debug("Storing new trims: %s", new_trims)
                self.camera_options = {"trims_data": new_trims}
            else:
                # If the stored values are not all zero, reset the trims.
                reset_trims = coordinator.shared.trims.clear()
                LOGGER.debug("Resetting trims and offsets to defaults: %s", reset_trims)
                self.camera_options = {
                    "offset_bottom": 0,
                    "offset_left": 0,
                    "offset_top": 0,
                    "offset_right": 0,
                    "trims_data": reset_trims,
                }
            return await self.async_step_opt_save()

    async def async_step_opt_save(self):
        """
        Save the options in a sorted way. It stores all the options.
        """
        LOGGER.info(
            "Storing Updated Camera (%s) Options.", self.camera_config.unique_id
        )
        try:
            _, vacuum_device = get_vacuum_device_info(
                self.camera_config.data.get(CONF_VACUUM_CONFIG_ENTRY_ID), self.hass
            )
            opt_update = await update_options(self.backup_options, self.camera_options)
            LOGGER.debug("updated options:%s", dict(opt_update))
            return self.async_create_entry(
                title="",
                data=opt_update,
            )
        except Exception as e:
            LOGGER.error("Error in storing the options: %s", e, exc_info=True)
            return self.async_abort(reason="error")

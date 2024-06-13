"""config_flow 2024.06.4
IMPORTANT: Maintain code when adding new options to the camera
it will be mandatory to update const.py and common.py update_options.
Format of the new constants must be CONST_NAME = "const_name" update also
sting.json and en.json please.
"""

import logging
import os
import shutil
from typing import Any, Dict, Optional

from homeassistant import config_entries
from homeassistant.components.vacuum import DOMAIN as ZONE_VACUUM
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    BooleanSelector,
    ColorRGBSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.storage import STORAGE_DIR
import voluptuous as vol

from .common import (
    get_device_info,
    get_vacuum_mqtt_topic,
    get_vacuum_unique_id_from_mqtt_topic,
    update_options,
)
from .const import (
    ALPHA_BACKGROUND,
    ALPHA_CHARGER,
    ALPHA_GO_TO,
    ALPHA_MOVE,
    ALPHA_NO_GO,
    ALPHA_ROBOT,
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
    CONF_VACUUM_ENTITY_ID,
    CONF_ZOOM_LOCK_RATIO,
    DEFAULT_VALUES,
    DOMAIN,
    FONTS_AVAILABLE,
    IS_ALPHA,
    IS_ALPHA_R1,
    IS_ALPHA_R2,
    RATIO_VALUES,
    ROTATION_VALUES,
    TEXT_SIZE_VALUES,
)
from .utils.users_data import async_get_rooms_count, async_rename_room_description

_LOGGER = logging.getLogger(__name__)

VACUUM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VACUUM_ENTITY_ID): EntitySelector(
            EntitySelectorConfig(domain=ZONE_VACUUM),
        )
    }
)


class ValetudoCameraFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 3.1

    def __init__(self):
        self.data = {}
        self.options = {}
        self.name = ""

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        if user_input is not None:
            vacuum_entity_id = user_input["vacuum_entity"]
            entity_registry = er.async_get(self.hass)
            vacuum_entity = entity_registry.async_get(vacuum_entity_id)

            unique_id = get_vacuum_unique_id_from_mqtt_topic(
                get_vacuum_mqtt_topic(vacuum_entity_id, self.hass)
            )

            for existing_entity in self._async_current_entries():
                if (
                    existing_entity.data.get(CONF_VACUUM_ENTITY_ID) == vacuum_entity.id
                    or existing_entity.data.get(CONF_UNIQUE_ID) == unique_id
                ):
                    return self.async_abort(reason="already_configured")

            self.data.update(
                {
                    CONF_VACUUM_CONFIG_ENTRY_ID: vacuum_entity.id,
                    CONF_UNIQUE_ID: unique_id,
                    "platform": "valetudo_vacuum_camera",
                }
            )

            # set the unique_id in the entry configuration
            await self.async_set_unique_id(unique_id=unique_id)
            # set default options
            self.options.update(DEFAULT_VALUES)
            # create the path for storing the snapshots.
            storage_path = f"{self.hass.config.path(STORAGE_DIR)}/valetudo_camera"
            if not os.path.exists(storage_path):
                _LOGGER.debug(f"Creating the {storage_path} path.")
                try:
                    os.mkdir(storage_path)
                except FileExistsError as e:
                    _LOGGER.debug(f"Error {e} creating the path {storage_path}")
            else:
                _LOGGER.debug(f"Storage {storage_path} path found.")
            # Finally set up the entry.
            _, vacuum_device = get_device_info(
                self.data[CONF_VACUUM_CONFIG_ENTRY_ID], self.hass
            )

            # Return the data and default options to config_entry
            return self.async_create_entry(
                title=vacuum_device.name + " Camera",
                data=self.data,
                options=self.options,
            )

        return self.async_show_form(step_id="user", data_schema=VACUUM_SCHEMA)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.unique_id = self.config_entry.unique_id
        self.options = {}
        self.bk_options = self.config_entry.options
        self.file_name = self.unique_id.split("_")[0].lower()
        self._check_alpha = False
        _LOGGER.debug(
            "Options edit in progress.. options before edit: %s", dict(self.bk_options)
        )
        options_values = list(self.config_entry.options.values())
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
            self.IMG_SCHEMA = vol.Schema(
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
                        IS_ALPHA, default=self._check_alpha
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

    async def async_step_init(self, user_input=None):
        """
        Start the options menu configuration.
        """
        _LOGGER.info(f"{self.config_entry.unique_id}: Options Configuration Started.")
        errors = {}
        number_of_rooms = await async_get_rooms_count(self.file_name)
        if user_input is not None and "camera_config_action" in user_input:
            next_action = user_input["camera_config_action"]
            if next_action == "opt_1":
                return await self.async_step_image_opt()
            elif next_action == "opt_2":
                return await self.async_step_base_colours()
            elif next_action == "opt_3":
                return (
                    await self.async_step_rooms_colours_1()
                )  # self.async_step_rooms_colours_1()
            elif next_action == "opt_4":
                return await self.async_step_rooms_colours_2()
            elif next_action == "opt_5":
                return await self.async_step_advanced()
            elif next_action == "more options":
                """
                From TAPO custom control component, this is,
                a great idea of how to simply the configuration
                simple old style menu ;).
                """
            else:
                errors["base"] = "incorrect_options_action"

        # noinspection PyArgumentList
        if number_of_rooms > 8:
            menu_keys = SelectSelectorConfig(
                options=[
                    {"label": "configure_image", "value": "opt_1"},
                    {"label": "configure_general_colours", "value": "opt_2"},
                    {"label": "configure_rooms_colours_1", "value": "opt_3"},
                    {"label": "configure_rooms_colours_2", "value": "opt_4"},
                    {"label": "advanced_options", "value": "opt_5"},
                ],
                mode=SelectSelectorMode.LIST,
                translation_key="camera_config_action",
            )
        else:
            menu_keys = SelectSelectorConfig(
                options=[
                    {"label": "configure_image", "value": "opt_1"},
                    {"label": "configure_general_colours", "value": "opt_2"},
                    {"label": "configure_rooms_colours_1", "value": "opt_3"},
                    {"label": "advanced_options", "value": "opt_5"},
                ],
                mode=SelectSelectorMode.LIST,
                translation_key="camera_config_action",
            )

        data_schema = {"camera_config_action": SelectSelector(menu_keys)}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_advanced(self, user_input=None):
        """
        Start the options menu configuration.
        """
        errors = {}
        if user_input is not None and "camera_config_advanced" in user_input:
            next_action = user_input["camera_config_advanced"]
            if next_action == "opt_1":
                return await self.async_step_image_offset()
            elif next_action == "opt_2":
                return await self.async_step_status_text()
            elif next_action == "opt_3":
                return await self.async_step_download_logs()
            elif next_action == "opt_4":
                return await self.async_rename_translations()
            elif next_action == "more options":
                """
                From TAPO custom control component, this is,
                a great idea of how to simply the configuration
                simple old style menu ;).
                """
            else:
                errors["base"] = "incorrect_options_action"

        # noinspection PyArgumentList
        menu_keys_1 = SelectSelectorConfig(
            options=[
                {"label": "configure_image", "value": "opt_1"},
                {"label": "configure_status_text", "value": "opt_2"},
                {"label": "copy_camera_logs_to_www", "value": "opt_3"},
                {"label": "rename_colours_descriptions", "value": "opt_4"},
            ],
            mode=SelectSelectorMode.LIST,
            translation_key="camera_config_advanced",
        )

        data_schema = {"camera_config_advanced": SelectSelector(menu_keys_1)}

        return self.async_show_form(
            step_id="advanced",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_image_opt(self, user_input: Optional[Dict[str, Any]] = None):
        """
        Images Options Configuration
        """
        # "get_svg_file": user_input.get(CONF_EXPORT_SVG),
        if user_input is not None:
            self.options.update(
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
            data_schema=self.IMG_SCHEMA,
            description_placeholders=self.options,
        )

    async def async_step_image_offset(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """
        Images Offset Configuration
        """
        if user_input is not None:
            self.options.update(
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
            description_placeholders=self.options,
        )

    async def async_step_status_text(self, user_input: Optional[Dict[str, Any]] = None):
        """
        Images Status Text Configuration
        """
        if user_input is not None:
            self.options.update(
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
            description_placeholders=self.options,
        )

    async def async_step_base_colours(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """
        Base Colours Configuration.
        """
        _LOGGER.debug("Base Colours Configuration Started")
        if user_input is not None:
            self.options.update(
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
            self._check_alpha = user_input.get(IS_ALPHA)
            if self._check_alpha:
                self._check_alpha = False
                return await self.async_step_alpha_1()
            else:
                return await self.async_step_opt_save()

        return self.async_show_form(
            step_id="base_colours",
            data_schema=self.COLOR_BASE_SCHEMA,
            description_placeholders=self.options,
        )

    async def async_step_alpha_1(self, user_input: Optional[Dict[str, Any]] = None):
        """
        Transparency Configuration for the Base Colours
        """
        _LOGGER.debug("Base Colours Alpha Configuration Started")
        if user_input is not None:
            self.options.update(
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
            description_placeholders=self.options,
        )

    async def async_step_rooms_colours_1(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """Dynamically generate rooms colours configuration step based on the number of rooms."""
        _LOGGER.info("Dynamic Rooms Colours Configuration Started.")
        number_of_rooms = await async_get_rooms_count(self.file_name)
        rooms_count = 1
        if number_of_rooms > 8:
            rooms_count = 8
        elif (number_of_rooms <= 8) and (number_of_rooms != 0):
            rooms_count = number_of_rooms

        if user_input is not None:
            # Update options based on user input
            for i in range(rooms_count):
                room_key = f"color_room_{i}"
                self.options.update({room_key: user_input.get(room_key)})

            self._check_alpha = user_input.get(IS_ALPHA_R1, False)

            if self._check_alpha:
                return await self.async_step_alpha_2()
            else:
                return await self.async_step_opt_save()

        # Dynamically create data schema based on the number of rooms
        fields = {}
        for i in range(rooms_count):
            fields[
                vol.Optional(
                    f"color_room_{i}",
                    default=self.config_entry.options.get(f"color_room_{i}"),
                )
            ] = ColorRGBSelector()

        fields[vol.Optional(IS_ALPHA_R1, default=self._check_alpha)] = BooleanSelector()

        return self.async_show_form(
            step_id="rooms_colours_1",
            data_schema=vol.Schema(fields),
            description_placeholders=self.options,
        )

    async def async_step_rooms_colours_2(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """Dynamically generate rooms colours configuration step based on the number of rooms."""
        _LOGGER.info("Dynamic Rooms Colours over 8 Configuration Started.")
        number_of_rooms = await async_get_rooms_count(self.file_name)
        if user_input is not None:
            # Update options based on user input
            for i in range(8, min(number_of_rooms, 16)):
                room_key = f"color_room_{i}"
                self.options.update({room_key: user_input.get(room_key)})

            self._check_alpha = user_input.get(IS_ALPHA_R2, False)

            if self._check_alpha:
                return await self.async_step_alpha_3()
            else:
                return await self.async_step_opt_save()

        # Dynamically create data schema based on the number of rooms
        fields = {}
        for i in range(8, min(number_of_rooms, 16)):
            fields[
                vol.Optional(
                    f"color_room_{i}",
                    default=self.config_entry.options.get(f"color_room_{i}"),
                )
            ] = ColorRGBSelector()

        fields[vol.Optional(IS_ALPHA_R2, default=self._check_alpha)] = BooleanSelector()

        return self.async_show_form(
            step_id="rooms_colours_2",
            data_schema=vol.Schema(fields),
            description_placeholders=self.options,
        )

    async def async_step_alpha_2(self, user_input: Optional[Dict[str, Any]] = None):
        """Dynamically generate rooms colours configuration step based on the number of rooms."""
        _LOGGER.info("Dynamic Rooms Colours Configuration Started.")
        number_of_rooms = await async_get_rooms_count(self.file_name)
        rooms_count = 1
        if number_of_rooms > 8:
            rooms_count = 8
        elif (number_of_rooms <= 8) and (number_of_rooms != 0):
            rooms_count = number_of_rooms

        if user_input is not None:
            # Update options based on user input
            for i in range(rooms_count):
                room_key = f"alpha_room_{i}"
                self.options.update({room_key: user_input.get(room_key)})

            return await self.async_step_opt_save()

        # Dynamically create data schema based on the number of rooms
        fields = {}
        for i in range(rooms_count):
            fields[
                vol.Optional(
                    f"alpha_room_{i}",
                    default=self.config_entry.options.get(f"alpha_room_{i}"),
                )
            ] = NumberSelector(self.config_dict)

        return self.async_show_form(
            step_id="alpha_2",
            data_schema=vol.Schema(fields),
            description_placeholders=self.options,
        )

    async def async_step_alpha_3(self, user_input: Optional[Dict[str, Any]] = None):
        """Dynamically generate rooms colours configuration step based on the number of rooms."""
        _LOGGER.info("Dynamic Rooms Colours Configuration Started.")
        number_of_rooms = await async_get_rooms_count(self.file_name)
        if user_input is not None:
            # Update options based on user input
            for i in range(8, min(number_of_rooms, 16)):
                room_key = f"alpha_room_{i}"
                self.options.update({room_key: user_input.get(room_key)})

            return await self.async_step_opt_save()

        # Dynamically create data schema based on the number of rooms
        fields = {}
        for i in range(8, min(number_of_rooms, 16)):
            fields[
                vol.Optional(
                    f"alpha_room_{i}",
                    default=self.config_entry.options.get(f"alpha_room_{i}"),
                )
            ] = NumberSelector(self.config_dict)

        return self.async_show_form(
            step_id="alpha_3",
            data_schema=vol.Schema(fields),
            description_placeholders=self.options,
        )

    async def async_step_logs_move(self):
        """
        Move the logs from www config folder to .storage.
        """
        ha_dir = self.hass.config.path()
        ha_storage = self.hass.config.path(STORAGE_DIR)
        file_name = f"{self.file_name}.zip"
        source_path = f"{ha_storage}/valetudo_camera/{file_name}"
        destination_path = f"{ha_dir}/www/{file_name}"
        if os.path.exists(source_path):
            _LOGGER.info(f"Logs found in {source_path}")
            shutil.copy(source_path, destination_path)
        else:
            _LOGGER.debug(f"Logs not found in {source_path}")
        self.options = self.bk_options
        return await self.async_step_opt_save()

    async def async_step_logs_remove(self):
        """
        Remove the logs from www config folder.
        """
        ha_dir = self.hass.config.path()
        camera_id = self.unique_id.split("_")
        file_name = camera_id[0].lower() + ".zip"
        destination_path = f"{ha_dir}/www/{file_name}"
        if os.path.exists(destination_path):
            _LOGGER.info(f"Logs removed: {destination_path}")
            os.remove(destination_path)
        else:
            _LOGGER.debug(f"Logs not found: {destination_path}")
        self.options = self.bk_options
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
            elif next_action == "opt_2":
                return await self.async_step_logs_remove()
            elif next_action == "no_action":
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

    async def async_rename_translations(self):
        """
        Copy the logs from .storage to www config folder.
        """
        hass = self.hass
        user_input = None
        storage_path = hass.config.path(STORAGE_DIR, "valetudo_camera")
        _LOGGER.debug(f"Looking for Storage Path: {storage_path}")
        if (user_input is None) and self.bk_options:
            if self.hass:
                await hass.async_add_executor_job(
                    async_rename_room_description, hass, storage_path, self.file_name
                )
                self.options = self.bk_options
            return await self.async_step_opt_save()

        return self.async_show_form(step_id="rename_translations")

    async def async_step_opt_save(self):
        """
        Save the options in a sorted way. It stores all the options.
        """
        _LOGGER.info(f"Storing Updated Camera ({self.config_entry.unique_id}) Options.")
        _, vacuum_device = get_device_info(
            self.config_entry.data.get(CONF_VACUUM_CONFIG_ENTRY_ID), self.hass
        )
        opt_update = await update_options(self.bk_options, self.options)
        _LOGGER.debug(f"updated options:{dict(opt_update)}")
        return self.async_create_entry(
            title="",
            data=opt_update,
        )

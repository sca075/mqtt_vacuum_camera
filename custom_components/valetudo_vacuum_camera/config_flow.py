"""config_flow ver.1.6.0
IMPORTANT: When adding new options to the camera
it will be mandatory to update const.py update_options.
Format of the new constants must be CONST_NAME = "const_name" update also
sting.json and en.json please.
"""

import logging
import os
import shutil
from typing import Any, Dict, Optional

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.vacuum import DOMAIN as ZONE_VACUUM
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
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

from .common import (  # get_entity_identifier_from_mqtt,
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
    ALPHA_ROOM_0,
    ALPHA_ROOM_1,
    ALPHA_ROOM_2,
    ALPHA_ROOM_3,
    ALPHA_ROOM_4,
    ALPHA_ROOM_5,
    ALPHA_ROOM_6,
    ALPHA_ROOM_7,
    ALPHA_ROOM_8,
    ALPHA_ROOM_9,
    ALPHA_ROOM_10,
    ALPHA_ROOM_11,
    ALPHA_ROOM_12,
    ALPHA_ROOM_13,
    ALPHA_ROOM_14,
    ALPHA_ROOM_15,
    ALPHA_TEXT,
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
    COLOR_ROOM_1,
    COLOR_ROOM_2,
    COLOR_ROOM_3,
    COLOR_ROOM_4,
    COLOR_ROOM_5,
    COLOR_ROOM_6,
    COLOR_ROOM_7,
    COLOR_ROOM_8,
    COLOR_ROOM_9,
    COLOR_ROOM_10,
    COLOR_ROOM_11,
    COLOR_ROOM_12,
    COLOR_ROOM_13,
    COLOR_ROOM_14,
    COLOR_ROOM_15,
    COLOR_TEXT,
    COLOR_WALL,
    COLOR_ZONE_CLEAN,
    CONF_ASPECT_RATIO,
    CONF_AUTO_ZOOM,
    CONF_ZOOM_LOCK_RATIO,
    # CONF_EXPORT_SVG,
    CONF_SNAPSHOTS_ENABLE,
    CONF_VAC_STAT,
    CONF_VAC_STAT_FONT,
    CONF_VAC_STAT_POS,
    CONF_VAC_STAT_SIZE,
    CONF_VACUUM_CONFIG_ENTRY_ID,
    CONF_VACUUM_ENTITY_ID,
    DOMAIN,
    IS_ALPHA,
    IS_ALPHA_R1,
    IS_ALPHA_R2,
)

_LOGGER = logging.getLogger(__name__)

VACUUM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VACUUM_ENTITY_ID): EntitySelector(
            EntitySelectorConfig(domain=ZONE_VACUUM),
        )
    }
)


class ValetudoCameraFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2.4

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
            await self.async_set_unique_id(unique_id=unique_id, raise_on_progress=True)
            # set default options
            self.options.update(
                {
                    "rotate_image": "0",
                    "margins": "100",
                    "aspect_ratio": "None",
                    "auto_zoom": False,
                    "zoom_lock_ratio": True,
                    "show_vac_status": False,
                    "vac_status_font": "custom_components/valetudo_vacuum_camera/utils/fonts/FiraSans.ttf",
                    "vac_status_size": 50,
                    "vac_status_position": True,
                    "get_svg_file": False,
                    "enable_www_snapshots": False,
                    "color_charger": [255, 128, 0],
                    "color_move": [238, 247, 255],
                    "color_wall": [255, 255, 0],
                    "color_robot": [255, 255, 204],
                    "color_go_to": [0, 255, 0],
                    "color_no_go": [255, 0, 0],
                    "color_zone_clean": [255, 255, 255],
                    "color_background": [0, 125, 255],
                    "color_text": [255, 255, 255],
                    "alpha_charger": 255.0,
                    "alpha_move": 255.0,
                    "alpha_wall": 255.0,
                    "alpha_robot": 255.0,
                    "alpha_go_to": 255.0,
                    "alpha_no_go": 125.0,
                    "alpha_zone_clean": 125.0,
                    "alpha_background": 255.0,
                    "alpha_text": 255.0,
                    "color_room_0": [135, 206, 250],
                    "color_room_1": [176, 226, 255],
                    "color_room_2": [165, 105, 18],
                    "color_room_3": [164, 211, 238],
                    "color_room_4": [141, 182, 205],
                    "color_room_5": [96, 123, 139],
                    "color_room_6": [224, 255, 255],
                    "color_room_7": [209, 238, 238],
                    "color_room_8": [180, 205, 205],
                    "color_room_9": [122, 139, 139],
                    "color_room_10": [175, 238, 238],
                    "color_room_11": [84, 153, 199],
                    "color_room_12": [133, 193, 233],
                    "color_room_13": [245, 176, 65],
                    "color_room_14": [82, 190, 128],
                    "color_room_15": [72, 201, 176],
                    "alpha_room_0": 255.0,
                    "alpha_room_1": 255.0,
                    "alpha_room_2": 255.0,
                    "alpha_room_3": 255.0,
                    "alpha_room_4": 255.0,
                    "alpha_room_5": 255.0,
                    "alpha_room_6": 255.0,
                    "alpha_room_7": 255.0,
                    "alpha_room_8": 255.0,
                    "alpha_room_9": 255.0,
                    "alpha_room_10": 255.0,
                    "alpha_room_11": 255.0,
                    "alpha_room_12": 255.0,
                    "alpha_room_13": 255.0,
                    "alpha_room_14": 255.0,
                    "alpha_room_15": 255.0,
                }
            )

            # Finally set up the entry.
            _, vacuum_device = get_device_info(
                self.data[CONF_VACUUM_CONFIG_ENTRY_ID], self.hass
            )

            # Return the data and options to config_entry
            # This to duplicate the data recreating the options
            # in the options flow.

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
        self._check_alpha = False
        _LOGGER.debug(
            "Options edit in progress.. options before edit: %s", dict(self.bk_options)
        )
        options_values = list(self.config_entry.options.values())
        if len(options_values) > 0:
            config_dict: NumberSelectorConfig = {
                "min": 0.0,  # Minimum value
                "max": 255.0,  # Maximum value
                "step": 1.0,  # Step value
            }
            config_size: NumberSelectorConfig = {
                "min": 5,  # Minimum value
                "max": 51,  # Maximum value
                "step": 1,  # Step value
            }
            font_selector = SelectSelectorConfig(
                options=[
                    {
                        "label": "Fira Sans",
                        "value": "custom_components/valetudo_vacuum_camera/utils/fonts/FiraSans.ttf",
                    },
                    {
                        "label": "Inter",
                        "value": "custom_components/valetudo_vacuum_camera/utils/fonts/Inter-VF.ttf",
                    },
                    {
                        "label": "M Plus Regular",
                        "value": "custom_components/valetudo_vacuum_camera/utils/fonts/MPLUSRegular.ttf",
                    },
                    {
                        "label": "Noto Sans CJKhk",
                        "value": "custom_components/valetudo_vacuum_camera/utils/fonts/NotoSansCJKhk-VF.ttf",
                    },
                    {
                        "label": "Noto Kufi Arabic",
                        "value": "custom_components/valetudo_vacuum_camera/utils/fonts/NotoKufiArabic-VF.ttf",
                    },
                    {
                        "label": "Noto Sans Khojki",
                        "value": "custom_components/valetudo_vacuum_camera/utils/fonts/NotoSansKhojki.ttf",
                    },
                    {
                        "label": "Lato Regular",
                        "value": "custom_components/valetudo_vacuum_camera/utils/fonts/Lato-Regular.ttf",
                    },
                ],
                mode=SelectSelectorMode.DROPDOWN,
            )
            rotation_selector = SelectSelectorConfig(
                options=[
                    {"label": "0", "value": "0"},
                    {"label": "90", "value": "90"},
                    {"label": "180", "value": "180"},
                    {"label": "270", "value": "270"},
                ],
                mode=SelectSelectorMode.DROPDOWN,
            )
            aspec_ratio_selector = SelectSelectorConfig(
                options=[
                    {"label": "Original Ratio.", "value": "None"},
                    {"label": "1:1", "value": "1, 1"},
                    {"label": "2:1", "value": "2, 1"},
                    {"label": "3:2", "value": "3, 2"},
                    {"label": "5:4", "value": "5, 4"},
                    {"label": "9:16", "value": "9, 16"},
                    {"label": "16:9", "value": "16, 9"},
                ],
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
                    # vol.Optional(
                    #     CONF_EXPORT_SVG,
                    #     default=config_entry.options.get(CONF_EXPORT_SVG, False),
                    # ): BooleanSelector(),
                    vol.Optional(
                        CONF_SNAPSHOTS_ENABLE,
                        default=config_entry.options.get(CONF_SNAPSHOTS_ENABLE, True),
                    ): BooleanSelector(),
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
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_ZONE_CLEAN,
                        default=config_entry.options.get("alpha_zone_clean"),
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_WALL, default=config_entry.options.get("alpha_wall")
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_ROBOT, default=config_entry.options.get("alpha_robot")
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_CHARGER, default=config_entry.options.get("alpha_charger")
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_MOVE, default=config_entry.options.get("alpha_move")
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_GO_TO, default=config_entry.options.get("alpha_go_to")
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_NO_GO, default=config_entry.options.get("alpha_no_go")
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_TEXT, default=config_entry.options.get("alpha_text")
                    ): NumberSelector(config_dict),
                }
            )

            self.COLOR_ROOMS2_SCHEMA = vol.Schema(
                {
                    vol.Optional(
                        COLOR_ROOM_8, default=config_entry.options.get("color_room_8")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_9, default=config_entry.options.get("color_room_9")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_10, default=config_entry.options.get("color_room_10")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_11, default=config_entry.options.get("color_room_11")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_12, default=config_entry.options.get("color_room_12")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_13, default=config_entry.options.get("color_room_13")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_14, default=config_entry.options.get("color_room_14")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_15, default=config_entry.options.get("color_room_15")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        IS_ALPHA_R2, default=self._check_alpha
                    ): BooleanSelector(),
                }
            )

            self.COLOR_ROOMS1_SCHEMA = vol.Schema(
                {
                    vol.Optional(
                        COLOR_ROOM_0, default=config_entry.options.get("color_room_0")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_1, default=config_entry.options.get("color_room_1")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_2, default=config_entry.options.get("color_room_2")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_3, default=config_entry.options.get("color_room_3")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_4, default=config_entry.options.get("color_room_4")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_5, default=config_entry.options.get("color_room_5")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_6, default=config_entry.options.get("color_room_6")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_7, default=config_entry.options.get("color_room_7")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        IS_ALPHA_R1, default=self._check_alpha
                    ): BooleanSelector(),
                }
            )

            self.ALPHA_2_SCHEMA = vol.Schema(
                {
                    vol.Optional(
                        ALPHA_ROOM_0,
                        default=config_entry.options.get("alpha_room_0"),
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_ROOM_1,
                        default=config_entry.options.get("alpha_room_1"),
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_ROOM_2, default=config_entry.options.get("alpha_room_2")
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_ROOM_3, default=config_entry.options.get("alpha_room_3")
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_ROOM_4, default=config_entry.options.get("alpha_room_4")
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_ROOM_5, default=config_entry.options.get("alpha_room_5")
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_ROOM_6, default=config_entry.options.get("alpha_room_6")
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_ROOM_7, default=config_entry.options.get("alpha_room_7")
                    ): NumberSelector(config_dict),
                }
            )

            self.ALPHA_3_SCHEMA = vol.Schema(
                {
                    vol.Optional(
                        ALPHA_ROOM_8, default=config_entry.options.get("alpha_room_8")
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_ROOM_9, default=config_entry.options.get("alpha_room_9")
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_ROOM_10, default=config_entry.options.get("alpha_room_10")
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_ROOM_11, default=config_entry.options.get("alpha_room_11")
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_ROOM_12, default=config_entry.options.get("alpha_room_12")
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_ROOM_13, default=config_entry.options.get("alpha_room_13")
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_ROOM_14, default=config_entry.options.get("alpha_room_14")
                    ): NumberSelector(config_dict),
                    vol.Optional(
                        ALPHA_ROOM_15, default=config_entry.options.get("alpha_room_15")
                    ): NumberSelector(config_dict),
                }
            )

    async def async_step_init(self, user_input=None):
        """
        Start the options menu configuration.
        """
        _LOGGER.info(f"{self.config_entry.unique_id}: Options Configuration Started.")
        errors = {}
        if user_input is not None:
            if "camera_config_action" in user_input:
                next_action = user_input["camera_config_action"]
                if next_action == "opt_1":
                    return await self.async_step_image_opt()
                elif next_action == "opt_2":
                    return await self.async_step_status_text()
                elif next_action == "opt_3":
                    return await self.async_step_base_colours()
                elif next_action == "opt_4":
                    return await self.async_step_rooms_colours_1()
                elif next_action == "opt_5":
                    return await self.async_step_rooms_colours_2()
                elif next_action == "opt_6":
                    return await self.async_download_logs()
                elif next_action == "More Options":
                    """
                    From TAPO custom control component, this is,
                    a great idea of how to simply the configuration
                    simple old style menu ;).
                    """
                else:
                    errors["base"] = "incorrect_options_action"

        # noinspection PyArgumentList
        menu_keys = SelectSelectorConfig(
            options=[
                {"label": "configure_image", "value": "opt_1"},
                {"label": "configure_status_text", "value": "opt_2"},
                {"label": "configure_general_colours", "value": "opt_3"},
                {"label": "configure_rooms_colours_1", "value": "opt_4"},
                {"label": "configure_rooms_colours_2", "value": "opt_5"},
                {"label": "copy_camera_logs_to_www", "value": "opt_6"},
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
        """
        Rooms 1 to 8 Colours Configuration.
        """
        _LOGGER.info("Rooms 1 to 8 Colours Configuration Started.")
        if user_input is not None:
            self.options.update(
                {
                    "color_room_0": user_input.get(COLOR_ROOM_0),
                    "color_room_1": user_input.get(COLOR_ROOM_1),
                    "color_room_2": user_input.get(COLOR_ROOM_2),
                    "color_room_3": user_input.get(COLOR_ROOM_3),
                    "color_room_4": user_input.get(COLOR_ROOM_4),
                    "color_room_5": user_input.get(COLOR_ROOM_5),
                    "color_room_6": user_input.get(COLOR_ROOM_6),
                    "color_room_7": user_input.get(COLOR_ROOM_7),
                }
            )

            self._check_alpha = user_input.get(IS_ALPHA_R1)

            if self._check_alpha:
                self._check_alpha = False
                return await self.async_step_alpha_2()
            else:
                return await self.async_step_opt_save()

        return self.async_show_form(
            step_id="rooms_colours_1",
            data_schema=self.COLOR_ROOMS1_SCHEMA,
            description_placeholders=self.options,
        )

    async def async_step_rooms_colours_2(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """
        Rooms 9 to 15 Colours Configuration.
        """
        _LOGGER.info("Rooms 9 to 15 Colours Configuration Started.")
        if user_input is not None:
            self.options.update(
                {
                    "color_room_8": user_input.get(COLOR_ROOM_8),
                    "color_room_9": user_input.get(COLOR_ROOM_9),
                    "color_room_10": user_input.get(COLOR_ROOM_10),
                    "color_room_11": user_input.get(COLOR_ROOM_11),
                    "color_room_12": user_input.get(COLOR_ROOM_12),
                    "color_room_13": user_input.get(COLOR_ROOM_13),
                    "color_room_14": user_input.get(COLOR_ROOM_14),
                    "color_room_15": user_input.get(COLOR_ROOM_15),
                }
            )

            self._check_alpha = user_input.get(IS_ALPHA_R2)

            if self._check_alpha:
                self._check_alpha = False
                return await self.async_step_alpha_3()
            else:
                return await self.async_step_opt_save()

        return self.async_show_form(
            step_id="rooms_colours_2",
            data_schema=self.COLOR_ROOMS2_SCHEMA,
            description_placeholders=self.options,
        )

    async def async_step_alpha_2(self, user_input: Optional[Dict[str, Any]] = None):
        """
        Transparency Configuration for the Rooms 1 to 8.
        """
        _LOGGER.info("Rooms 1 to 8 Alpha Configuration Started")
        if user_input is not None:
            self.options.update(
                {
                    "alpha_room_0": user_input.get(ALPHA_ROOM_0),
                    "alpha_room_1": user_input.get(ALPHA_ROOM_1),
                    "alpha_room_2": user_input.get(ALPHA_ROOM_2),
                    "alpha_room_3": user_input.get(ALPHA_ROOM_3),
                    "alpha_room_4": user_input.get(ALPHA_ROOM_4),
                    "alpha_room_5": user_input.get(ALPHA_ROOM_5),
                    "alpha_room_6": user_input.get(ALPHA_ROOM_6),
                    "alpha_room_7": user_input.get(ALPHA_ROOM_7),
                }
            )

            return await self.async_step_opt_save()

        return self.async_show_form(
            step_id="alpha_2",
            data_schema=self.ALPHA_2_SCHEMA,
            description_placeholders=self.options,
        )

    async def async_step_alpha_3(self, user_input: Optional[Dict[str, Any]] = None):
        """
        Transparency Configuration for Rooms 9 to 15.
        """
        _LOGGER.info("Rooms 9 to 15 Alpha Configuration Started")
        if user_input is not None:
            self.options.update(
                {
                    "alpha_room_8": user_input.get(ALPHA_ROOM_8),
                    "alpha_room_9": user_input.get(ALPHA_ROOM_9),
                    "alpha_room_10": user_input.get(ALPHA_ROOM_10),
                    "alpha_room_11": user_input.get(ALPHA_ROOM_11),
                    "alpha_room_12": user_input.get(ALPHA_ROOM_12),
                    "alpha_room_13": user_input.get(ALPHA_ROOM_13),
                    "alpha_room_14": user_input.get(ALPHA_ROOM_14),
                    "alpha_room_15": user_input.get(ALPHA_ROOM_15),
                }
            )

            return await self.async_step_opt_save()

        return self.async_show_form(
            step_id="alpha_3",
            data_schema=self.ALPHA_3_SCHEMA,
            description_placeholders=self.options,
        )

    async def async_download_logs(self):
        """
        Copy the logs from .storage to www config folder.
        """
        user_input = None
        ha_dir = os.getcwd()
        ha_storage = STORAGE_DIR
        camera_id = self.unique_id.split("_")
        file_name = camera_id[0].lower() + ".zip"
        source_path = ha_dir + "/" + ha_storage + "/" + file_name
        destination_path = ha_dir + "/" + "www" + "/" + file_name
        if user_input is None:
            shutil.copy(source_path, destination_path)
            return await self.async_step_init()
        return self.async_show_form(step_id="download")

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

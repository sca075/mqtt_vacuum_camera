"""config_flow ver.1.4.7
IMPORTANT: When adding new options to the camera
it will be mandatory to update const.py update_options.
Format of the new constants must be CONST_NAME = "const_name" update also
sting.json and en.json please.
"""
import voluptuous as vol
import logging
from typing import Any, Dict, Optional
from homeassistant import config_entries

from homeassistant.components.vacuum import DOMAIN as ZONE_VACUUM
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    ColorRGBSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    BooleanSelector,
)
from homeassistant.helpers import entity_registry as er
from .const import (
    DOMAIN,
    ATTR_ROTATE,
    ATTR_CROP,
    ATTR_TRIM_LEFT,
    ATTR_TRIM_RIGHT,
    ATTR_TRIM_TOP,
    ATTR_TRIM_BOTTOM,
    CONF_VAC_STAT,
    CONF_SNAPSHOTS_ENABLE,
    CONF_VACUUM_CONFIG_ENTRY_ID,
    CONF_VACUUM_ENTITY_ID,
    COLOR_MOVE,
    COLOR_ROBOT,
    COLOR_WALL,
    COLOR_CHARGER,
    COLOR_BACKGROUND,
    COLOR_GO_TO,
    COLOR_NO_GO,
    COLOR_ZONE_CLEAN,
    COLOR_TEXT,
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
    IS_ALPHA, IS_ALPHA_R,
    ALPHA_BACKGROUND,
    ALPHA_CHARGER,
    ALPHA_MOVE,
    ALPHA_NO_GO,
    ALPHA_WALL,
    ALPHA_ROBOT,
    ALPHA_TEXT,
    ALPHA_GO_TO,
    ALPHA_ZONE_CLEAN,
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
)
from .common import (
    # get_entity_identifier_from_mqtt,
    get_device_info,
    get_vacuum_mqtt_topic,
    get_vacuum_unique_id_from_mqtt_topic,
    update_options
)

_LOGGER = logging.getLogger(__name__)

VACUUM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VACUUM_ENTITY_ID): EntitySelector(
            EntitySelectorConfig(domain=ZONE_VACUUM),
        )
    }
)

IMG_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ROTATE, default="0"): vol.In(["0", "90", "180", "270"]),
        vol.Required(ATTR_CROP, default="50"): cv.string,
        vol.Optional(ATTR_TRIM_TOP, default="0"): cv.string,
        vol.Optional(ATTR_TRIM_BOTTOM, default="0"): cv.string,
        vol.Optional(ATTR_TRIM_LEFT, default="0"): cv.string,
        vol.Optional(ATTR_TRIM_RIGHT, default="0"): cv.string,
        vol.Optional(CONF_VAC_STAT, default=False): BooleanSelector(),
    }
)

GENERIC_COLOR_SCHEMA = vol.Schema(
    {
        vol.Optional(COLOR_BACKGROUND, default=[0, 125, 255]): ColorRGBSelector(),
        vol.Optional(COLOR_ZONE_CLEAN, default=[255, 255, 255]): ColorRGBSelector(),
        vol.Optional(COLOR_WALL, default=[255, 255, 0]): ColorRGBSelector(),
        vol.Optional(COLOR_ROBOT, default=[255, 255, 204]): ColorRGBSelector(),
        vol.Optional(COLOR_CHARGER, default=[255, 128, 0]): ColorRGBSelector(),
        vol.Optional(COLOR_MOVE, default=[238, 247, 255]): ColorRGBSelector(),
        vol.Optional(COLOR_GO_TO, default=[0, 255, 0]): ColorRGBSelector(),
        vol.Optional(COLOR_NO_GO, default=[255, 0, 0]): ColorRGBSelector(),
        vol.Optional(COLOR_TEXT, default=[255, 255, 255]): ColorRGBSelector(),
    }
)

ROOMS_COLOR_SCHEMA = vol.Schema(
    {
        vol.Optional(COLOR_ROOM_0, default=[135, 206, 250]): ColorRGBSelector(),
        vol.Optional(COLOR_ROOM_1, default=[176, 226, 255]): ColorRGBSelector(),
        vol.Optional(COLOR_ROOM_2, default=[165, 105, 18]): ColorRGBSelector(),
        vol.Optional(COLOR_ROOM_3, default=[164, 211, 238]): ColorRGBSelector(),
        vol.Optional(COLOR_ROOM_4, default=[141, 182, 205]): ColorRGBSelector(),
        vol.Optional(COLOR_ROOM_5, default=[96, 123, 139]): ColorRGBSelector(),
        vol.Optional(COLOR_ROOM_6, default=[224, 255, 255]): ColorRGBSelector(),
        vol.Optional(COLOR_ROOM_7, default=[209, 238, 238]): ColorRGBSelector(),
        vol.Optional(COLOR_ROOM_8, default=[180, 205, 205]): ColorRGBSelector(),
        vol.Optional(COLOR_ROOM_9, default=[122, 139, 139]): ColorRGBSelector(),
        vol.Optional(COLOR_ROOM_10, default=[175, 238, 238]): ColorRGBSelector(),
        vol.Optional(COLOR_ROOM_11, default=[84, 153, 199]): ColorRGBSelector(),
        vol.Optional(COLOR_ROOM_12, default=[133, 193, 233]): ColorRGBSelector(),
        vol.Optional(COLOR_ROOM_13, default=[245, 176, 65]): ColorRGBSelector(),
        vol.Optional(COLOR_ROOM_14, default=[82, 190, 128]): ColorRGBSelector(),
        vol.Optional(COLOR_ROOM_15, default=[72, 201, 176]): ColorRGBSelector(),
    }
)


class ValetudoCameraFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2.1

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
                }
            )

            # set the unique_id in the entry configuration
            await self.async_set_unique_id(unique_id=unique_id, raise_on_progress=True)

            return await self.async_step_options_1()

        return self.async_show_form(step_id="user", data_schema=VACUUM_SCHEMA)

    async def async_step_options_1(self, user_input: Optional[Dict[str, Any]] = None):
        if user_input is not None:
            self.options.update(
                {
                    "rotate_image": user_input.get(ATTR_ROTATE),
                    "crop_image": user_input.get(ATTR_CROP),
                    "trim_top": user_input.get(ATTR_TRIM_TOP),
                    "trim_bottom": user_input.get(ATTR_TRIM_BOTTOM),
                    "trim_left": user_input.get(ATTR_TRIM_LEFT),
                    "trim_right": user_input.get(ATTR_TRIM_RIGHT),
                    "show_vac_status": user_input.get(CONF_VAC_STAT),
                }
            )

            return await self.async_step_options_2()

        return self.async_show_form(
            step_id="options_1",
            data_schema=IMG_SCHEMA,
            description_placeholders=self.options,
        )

    async def async_step_options_2(self, user_input: Optional[Dict[str, Any]] = None):
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
                    "color_text": user_input.get(COLOR_TEXT),
                    "alpha_charger": 255.0,
                    "alpha_move": 255.0,
                    "alpha_wall": 255.0,
                    "alpha_robot": 255.0,
                    "alpha_go_to": 255.0,
                    "alpha_no_go": 25.0,
                    "alpha_zone_clean": 25.0,
                    "alpha_background": 255.0,
                    "alpha_text": 255.0,
                }
            )

            return await self.async_step_options_3()

        return self.async_show_form(
            step_id="options_2",
            data_schema=GENERIC_COLOR_SCHEMA,
            description_placeholders=self.options,
        )

    async def async_step_options_3(self, user_input: Optional[Dict[str, Any]] = None):
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
                    "color_room_8": user_input.get(COLOR_ROOM_8),
                    "color_room_9": user_input.get(COLOR_ROOM_9),
                    "color_room_10": user_input.get(COLOR_ROOM_10),
                    "color_room_11": user_input.get(COLOR_ROOM_11),
                    "color_room_12": user_input.get(COLOR_ROOM_12),
                    "color_room_13": user_input.get(COLOR_ROOM_13),
                    "color_room_14": user_input.get(COLOR_ROOM_14),
                    "color_room_15": user_input.get(COLOR_ROOM_15),
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

        return self.async_show_form(
            step_id="options_3",
            data_schema=ROOMS_COLOR_SCHEMA,
            description_placeholders=self.options,
        )

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
            "Options edit in progress.. options before edit: ",
            self.bk_options)
        options_values = list(self.config_entry.options.values())
        if len(options_values) > 0:
            config_dict: NumberSelectorConfig = {
                "min": 0.0,  # Minimum value
                "max": 255.0,  # Maximum value
                "step": 1.0,  # Step value
            }
            self.IMG_SCHEMA = vol.Schema(
                {
                    vol.Required(
                        ATTR_ROTATE, default=config_entry.options.get("rotate_image")
                    ): vol.In(["0", "90", "180", "270"]),
                    vol.Required(
                        ATTR_CROP, default=config_entry.options.get("crop_image")
                    ): cv.string,
                    vol.Optional(
                        ATTR_TRIM_TOP, default=config_entry.options.get("trim_top")
                    ): cv.string,
                    vol.Optional(
                        ATTR_TRIM_BOTTOM,
                        default=config_entry.options.get("trim_bottom"),
                    ): cv.string,
                    vol.Optional(
                        ATTR_TRIM_LEFT, default=config_entry.options.get("trim_left")
                    ): cv.string,
                    vol.Optional(
                        ATTR_TRIM_RIGHT, default=config_entry.options.get("trim_right")
                    ): cv.string,
                    vol.Optional(
                        CONF_VAC_STAT,
                        default=config_entry.options.get("show_vac_status"),
                    ): BooleanSelector(),
                    vol.Optional(
                        CONF_SNAPSHOTS_ENABLE,
                        default=config_entry.options.get(CONF_SNAPSHOTS_ENABLE, True),
                    ): BooleanSelector(),
                }
            )
            _LOGGER.debug("Defined Image Schema")
            self.COLOR_1_SCHEMA = vol.Schema(
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
                        COLOR_TEXT, default=config_entry.options.get("color_text")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        IS_ALPHA, default=self._check_alpha
                    ): BooleanSelector(),
                }
            )
            _LOGGER.debug("Defined Color 1 Schema")
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
            _LOGGER.debug("Defined Alpha 1 Schema")
            self.COLOR_2_SCHEMA = vol.Schema(
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
                        IS_ALPHA_R, default=self._check_alpha
                    ): BooleanSelector(),
                }
            )
            _LOGGER.debug("Defined Color 2 Schema")
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
            _LOGGER.debug("Defined Alpha 2 Schema")

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None):
        if user_input is not None:
            self.options.update(
                {
                    "rotate_image": user_input.get(ATTR_ROTATE),
                    "crop_image": user_input.get(ATTR_CROP),
                    "trim_top": user_input.get(ATTR_TRIM_TOP),
                    "trim_bottom": user_input.get(ATTR_TRIM_BOTTOM),
                    "trim_left": user_input.get(ATTR_TRIM_LEFT),
                    "trim_right": user_input.get(ATTR_TRIM_RIGHT),
                    "show_vac_status": user_input.get(CONF_VAC_STAT),
                    CONF_SNAPSHOTS_ENABLE: user_input.get(CONF_SNAPSHOTS_ENABLE),
                }
            )
            return await self.async_step_init_2()

        return self.async_show_form(
            step_id="init",
            data_schema=self.IMG_SCHEMA,
            description_placeholders=self.options,
        )

    async def async_step_init_2(self, user_input: Optional[Dict[str, Any]] = None):
        _LOGGER.debug("async_step_init_2 called")
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
                    "color_text": user_input.get(COLOR_TEXT),
                }
            )
            self._check_alpha = user_input.get(IS_ALPHA)

            if self._check_alpha:
                self._check_alpha = False
                return await self.async_step_alpha_1()
            else:
                return await self.async_step_init_3()

        _LOGGER.debug("self.data before show form: %s", self.options)
        return self.async_show_form(
            step_id="init_2",
            data_schema=self.COLOR_1_SCHEMA,
            description_placeholders=self.options,
        )

    async def async_step_alpha_1(self, user_input: Optional[Dict[str, Any]] = None):
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
            return await self.async_step_init_3()

        return self.async_show_form(
            step_id="alpha_1",
            data_schema=self.ALPHA_1_SCHEMA,
            description_placeholders=self.options,
        )

    async def async_step_init_3(self, user_input: Optional[Dict[str, Any]] = None):
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

            self._check_alpha = user_input.get(IS_ALPHA_R)

            if self._check_alpha:
                self._check_alpha = False
                return await self.async_step_alpha_2()
            else:
                opt_update = await update_options(self.bk_options, self.options)
                _LOGGER.debug("updated options:", opt_update)
                return self.async_create_entry(
                    title="",
                    data=opt_update,
                )

        return self.async_show_form(
            step_id="init_3",
            data_schema=self.COLOR_2_SCHEMA,
            description_placeholders=self.options,
        )

    async def async_step_alpha_2(self, user_input: Optional[Dict[str, Any]] = None):
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
            _, vacuum_device = get_device_info(
                self.config_entry.data.get(CONF_VACUUM_CONFIG_ENTRY_ID), self.hass
            )
            opt_update = await update_options(self.bk_options, self.options)
            _LOGGER.debug("updated options:", opt_update)
            return self.async_create_entry(
                title="",
                data=opt_update,
            )

        return self.async_show_form(
            step_id="alpha_2",
            data_schema=self.ALPHA_2_SCHEMA,
            description_placeholders=self.options,
        )

"""config_flow ver.1.3.4"""

import voluptuous as vol
import logging
from typing import Any, Dict, Optional
from homeassistant import config_entries

from homeassistant.components.vacuum import DOMAIN as ZONE_VACUUM
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    ColorRGBSelector,
    EntitySelector,
    EntitySelectorConfig,
)
from homeassistant.helpers import entity_registry as er
from .const import (
    DOMAIN,
    CONF_VACUUM_ENTITY_ID,
    ATTR_ROTATE,
    ATTR_CROP,
    ATTR_TRIM_LEFT,
    ATTR_TRIM_RIGHT,
    ATTR_TRIM_TOP,
    ATTR_TRIM_BOTTOM,
    CONF_VAC_STAT,
    CONF_VACUUM_CONFIG_ENTRY_ID,
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
)
from .common import get_device_info

_LOGGER = logging.getLogger(__name__)

VACUUM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VACUUM_ENTITY_ID): EntitySelector(
            EntitySelectorConfig(domain=ZONE_VACUUM)
        ),
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
        vol.Optional(CONF_VAC_STAT, default=False): cv.boolean,
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
    VERSION = 2.0

    def __init__(self):
        self.data = {}

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        if user_input is not None:
            vacuum_entity_id = user_input["vacuum_entity"]
            entity_registry = er.async_get(self.hass)
            vacuum_entity = entity_registry.async_get(vacuum_entity_id)
            self.data.update({CONF_VACUUM_CONFIG_ENTRY_ID: vacuum_entity.id})

            return await self.async_step_options_1()

        return self.async_show_form(step_id="user", data_schema=VACUUM_SCHEMA)

    async def async_step_options_1(self, user_input: Optional[Dict[str, Any]] = None):
        if user_input is not None:
            self.data.update(
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
            description_placeholders=self.data,
        )

    async def async_step_options_2(self, user_input: Optional[Dict[str, Any]] = None):
        if user_input is not None:
            self.data.update(
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

            return await self.async_step_options_3()

        return self.async_show_form(
            step_id="options_2",
            data_schema=GENERIC_COLOR_SCHEMA,
            description_placeholders=self.data,
        )

    async def async_step_options_3(self, user_input: Optional[Dict[str, Any]] = None):
        if user_input is not None:
            self.data.update(
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

            _, vacuum_device = get_device_info(
                self.data[CONF_VACUUM_CONFIG_ENTRY_ID], self.hass
            )

            return self.async_create_entry(
                title=vacuum_device.name + " Camera",
                data=self.data,
            )

        return self.async_show_form(
            step_id="options_3",
            data_schema=ROOMS_COLOR_SCHEMA,
            description_placeholders=self.data,
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
        _LOGGER.debug(list(self.config_entry.options.values()))
        options_values = list(self.config_entry.options.values())
        if len(options_values) > 0:
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
                    ): cv.boolean,
                }
            )
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
                }
            )
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
                }
            )
        else:
            self.IMG_SCHEMA = vol.Schema(
                {
                    vol.Required(
                        ATTR_ROTATE, default=config_entry.data.get("rotate_image")
                    ): vol.In(["0", "90", "180", "270"]),
                    vol.Required(
                        ATTR_CROP, default=config_entry.data.get("crop_image")
                    ): cv.string,
                    vol.Optional(
                        ATTR_TRIM_TOP, default=config_entry.data.get("trim_top")
                    ): cv.string,
                    vol.Optional(
                        ATTR_TRIM_BOTTOM, default=config_entry.data.get("trim_bottom")
                    ): cv.string,
                    vol.Optional(
                        ATTR_TRIM_LEFT, default=config_entry.data.get("trim_left")
                    ): cv.string,
                    vol.Optional(
                        ATTR_TRIM_RIGHT, default=config_entry.data.get("trim_right")
                    ): cv.string,
                    vol.Optional(
                        CONF_VAC_STAT, default=config_entry.data.get("show_vac_status")
                    ): cv.boolean,
                }
            )
            self.COLOR_1_SCHEMA = vol.Schema(
                {
                    vol.Optional(
                        COLOR_BACKGROUND,
                        default=config_entry.data.get("color_background"),
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ZONE_CLEAN,
                        default=config_entry.data.get("color_zone_clean"),
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_WALL, default=config_entry.data.get("color_wall")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROBOT, default=config_entry.data.get("color_robot")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_CHARGER, default=config_entry.data.get("color_charger")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_MOVE, default=config_entry.data.get("color_move")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_GO_TO, default=config_entry.data.get("color_go_to")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_NO_GO, default=config_entry.data.get("color_no_go")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_TEXT, default=config_entry.data.get("color_text")
                    ): ColorRGBSelector(),
                }
            )
            self.COLOR_2_SCHEMA = vol.Schema(
                {
                    vol.Optional(
                        COLOR_ROOM_0, default=config_entry.data.get("color_room_0")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_1, default=config_entry.data.get("color_room_1")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_2, default=config_entry.data.get("color_room_2")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_3, default=config_entry.data.get("color_room_3")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_4, default=config_entry.data.get("color_room_4")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_5, default=config_entry.data.get("color_room_5")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_6, default=config_entry.data.get("color_room_6")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_7, default=config_entry.data.get("color_room_7")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_8, default=config_entry.data.get("color_room_8")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_9, default=config_entry.data.get("color_room_9")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_10, default=config_entry.data.get("color_room_10")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_11, default=config_entry.data.get("color_room_11")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_12, default=config_entry.data.get("color_room_12")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_13, default=config_entry.data.get("color_room_13")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_14, default=config_entry.data.get("color_room_14")
                    ): ColorRGBSelector(),
                    vol.Optional(
                        COLOR_ROOM_15, default=config_entry.data.get("color_room_15")
                    ): ColorRGBSelector(),
                }
            )
        self.data = None

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None):
        self.data = user_input

        if user_input is not None:
            self.data.update(
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
            return await self.async_step_init_2()

        return self.async_show_form(
            step_id="init",
            data_schema=self.IMG_SCHEMA,
            description_placeholders=self.data,
        )

    async def async_step_init_2(self, user_input: Optional[Dict[str, Any]] = None):
        _LOGGER.debug("async_step_init_2 called")
        _LOGGER.debug(
            "color robot in the options: %s",
            self.config_entry.options.get("color_robot"),
        )
        if user_input is not None:
            self.data.update(
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

            return await self.async_step_init_3()
        _LOGGER.debug("self.data before show form: %s", self.data)
        return self.async_show_form(
            step_id="init_2",
            data_schema=self.COLOR_1_SCHEMA,
            description_placeholders=self.data,
        )

    async def async_step_init_3(self, user_input: Optional[Dict[str, Any]] = None):
        if user_input is not None:
            self.data.update(
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

            return self.async_create_entry(
                title="",
                data=self.data,
            )

        return self.async_show_form(
            step_id="init_3",
            data_schema=self.COLOR_2_SCHEMA,
            description_placeholders=self.data,
        )

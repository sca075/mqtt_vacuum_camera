"""config_flow ver.1.2.1"""

import voluptuous as vol
import logging
from typing import Any, Dict, Optional
from homeassistant import config_entries

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import EntitySelector, ColorRGBSelector
from .const import (
    DOMAIN,
    CONF_VACUUM_ENTITY_ID,
    CONF_VACUUM_CONNECTION_STRING,
    CONF_MQTT_USER,
    CONF_MQTT_PASS,
    ATTR_ROTATE,
    ATTR_CROP,
    COLOR_MOVE,
    COLOR_ROBOT,
    COLOR_WALL,
    COLOR_CHARGER,
    COLOR_BACKGROUND,
    COLOR_GO_TO,
    COLOR_NO_GO,
    COLOR_ZONE_CLEAN,
    CONF_COLORS,
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

_LOGGER = logging.getLogger(__name__)

VACUUM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VACUUM_ENTITY_ID): EntitySelector(),
    }
)

MQTT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MQTT_USER): cv.string,
        vol.Required(CONF_MQTT_PASS): cv.string,
        vol.Required(CONF_VACUUM_CONNECTION_STRING): cv.string,
    }
)

IMG_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ROTATE, default="0"): vol.In(["0", "90", "180", "270"]),
        vol.Required(ATTR_CROP, default="50"): cv.string,
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
    VERSION = 1.2

    def __init__(self):
        self.data = None

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        if user_input is not None:
            return await self.async_step_mqtt()

        return self.async_show_form(step_id="user", data_schema=VACUUM_SCHEMA)

    async def async_step_mqtt(self, user_input: Optional[Dict[str, Any]] = None):
        if user_input is not None:
            self.data = user_input
            return await self.async_step_options_1()

        return self.async_show_form(step_id="mqtt", data_schema=MQTT_SCHEMA)

    async def async_step_options_1(self, user_input: Optional[Dict[str, Any]] = None):
        if user_input is not None:
            self.data.update(
                {
                    "rotate_image": user_input.get(ATTR_ROTATE),
                    "crop_image": user_input.get(ATTR_CROP),
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
                }
            )

            # Update the USER_COLORS array with the user-defined colors
            CONF_COLORS[0] = self.data["color_wall"]
            CONF_COLORS[1] = self.data["color_zone_clean"]
            CONF_COLORS[2] = self.data["color_robot"]
            CONF_COLORS[3] = self.data["color_background"]
            CONF_COLORS[4] = self.data["color_move"]
            CONF_COLORS[5] = self.data["color_charger"]
            CONF_COLORS[6] = self.data["color_no_go"]
            CONF_COLORS[7] = self.data["color_go_to"]

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

            tmp_name = self.data["vacuum_map"]
            tmp_name = tmp_name.split("/")
            default_name = tmp_name[1] + " Camera"

            return self.async_create_entry(
                title=default_name,
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

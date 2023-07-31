"""config_flow ver.1.7.0"""

import voluptuous as vol
import logging
from typing import Any, Dict, Optional
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    EntitySelector,
    ColorRGBSelector
)

from .const import (
    DOMAIN,
    CONF_VACUUM_ENTITY_ID,
    CONF_VACUUM_CONNECTION_STRING,
    CONF_MQTT_USER,
    CONF_MQTT_PASS,
    DEFAULT_NAME,
    ATT_ROTATE,
    ATT_CROP,
    COLOR_MOVE,
    COLOR_ROBOT,
    COLOR_WALL,
    COLOR_CHARGER,
    COLOR_BACKGROUND,
    COLOR_GO_TO,
    COLOR_NO_GO,
    COLOR_ZONE_CLEAN,
    CONF_COLORS,
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
        vol.Required(ATT_ROTATE, default="0"): vol.In(["0", "90", "180", "270"]),
        vol.Required(ATT_CROP, default="50"): cv.string,
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


class ValetudoCameraFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1.1

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
                    "rotate_image": user_input.get(ATT_ROTATE),
                    "crop_image": user_input.get(ATT_CROP),
                }
            )

            return await self.async_step_options_2()

        return self.async_show_form(
            step_id="options_1", data_schema=IMG_SCHEMA, description_placeholders=self.data
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

            return self.async_create_entry(
                title=DEFAULT_NAME,
                data=self.data,
            )

        return self.async_show_form(
            step_id="options_2", data_schema=GENERIC_COLOR_SCHEMA, description_placeholders=self.data
        )

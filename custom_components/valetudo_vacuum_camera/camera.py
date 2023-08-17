"""Camera Version 1.3.2"""
from __future__ import annotations
import logging
import os
import json
from io import BytesIO
from datetime import datetime
from PIL import Image
from datetime import timedelta
from typing import Optional
import voluptuous as vol
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA, SUPPORT_ON_OFF
from homeassistant.const import CONF_NAME
from homeassistant import core, config_entries
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)
from homeassistant.util import Throttle
from custom_components.valetudo_vacuum_camera.valetudo.connector import (
    ValetudoConnector,
)
from custom_components.valetudo_vacuum_camera.valetudo.image_handler import (
    MapImageHandler,
)
from custom_components.valetudo_vacuum_camera.utils.colors import (
    base_colors_array,
    rooms_color,
    add_alpha_to_rgb,
)
from custom_components.valetudo_vacuum_camera.valetudo.vacuum import Vacuum
from .const import (
    CONF_VACUUM_CONNECTION_STRING,
    CONF_VACUUM_ENTITY_ID,
    CONF_MQTT_USER,
    CONF_MQTT_PASS,
    CONF_VAC_STAT,
    DEFAULT_NAME,
    DOMAIN,
    PLATFORMS,
    ATTR_ROTATE,
    ATTR_CROP,
    ATTR_TRIM_TOP,
    ATTR_TRIM_BOTTOM,
    ATTR_TRIM_LEFT,
    ATTR_TRIM_RIGHT,
    COLOR_WALL,
    COLOR_ZONE_CLEAN,
    COLOR_ROBOT,
    COLOR_BACKGROUND,
    COLOR_MOVE,
    COLOR_CHARGER,
    COLOR_TEXT,
    COLOR_NO_GO,
    COLOR_GO_TO,
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

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_VACUUM_CONNECTION_STRING): cv.string,
        vol.Required(CONF_VACUUM_ENTITY_ID): cv.string,
        vol.Required(CONF_MQTT_USER): cv.string,
        vol.Required(CONF_MQTT_PASS): cv.string,
        vol.Required(ATTR_ROTATE, default="0"): cv.string,
        vol.Required(ATTR_CROP, default="50"): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.entity_id,
    }
)
SCAN_INTERVAL = timedelta(seconds=6)
_LOGGER: logging.Logger = logging.getLogger(__name__)


async def async_setup_entry(
        hass: core.HomeAssistant,
        config_entry: config_entries.ConfigEntry,
        async_add_entities,
) -> None:
    """Setup camera from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    # Update our config to and eventually add or remove option.
    if config_entry.options:
        config.update(config_entry.options)
    camera = [ValetudoCamera(Camera, config)]
    async_add_entities(camera, update_before_add=True)


async def async_setup_platform(
        hass: HomeAssistantType,
        config: ConfigType,
        async_add_entities,
        discovery_info: DiscoveryInfoType | None = None,
):
    async_add_entities([ValetudoCamera(hass, config)])
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)


class ValetudoCamera(Camera, Entity):
    _attr_has_entity_name = True

    def __init__(self, hass, device_info):
        super().__init__()
        self.hass = hass
        self._vacuum_entity = device_info.get(CONF_VACUUM_ENTITY_ID)
        self._mqtt_listen_topic = device_info.get(CONF_VACUUM_CONNECTION_STRING)
        if self._mqtt_listen_topic:
            self._mqtt_listen_topic = str(self._mqtt_listen_topic)
            file_name = self._mqtt_listen_topic.split("/")
            self.snapshot_img = "/config/www/snapshot_" + file_name[1].lower() + ".png"
            self._attr_name = file_name[1] + " Camera"
            self._attr_unique_id = file_name[1].lower() + "_camera"
            self.file_name = file_name[1].lower()
        self._mqtt_user = device_info.get(CONF_MQTT_USER)
        self._mqtt_pass = device_info.get(CONF_MQTT_PASS)
        self._mqtt = ValetudoConnector(
            self._mqtt_user, self._mqtt_pass, self._mqtt_listen_topic, hass
        )
        self._map_handler = MapImageHandler()
        self._map_rooms = None
        self._vacuum_shared = Vacuum()
        self._vacuum_state = None
        self._frame_interval = 1
        self._vac_img_data = None
        self._vac_json_data = None
        self._vac_json_id = None
        self._attr_calibration_points = None
        self._base = None
        self._current = None
        self._temp_dir = "config/tmp"
        self._image_rotate = device_info.get(ATTR_ROTATE)
        if self._image_rotate:
            self._image_rotate = int(device_info.get(ATTR_ROTATE))
        else:
            self._image_rotate = 0
        self._image_crop = device_info.get(ATTR_CROP)
        if self._image_crop:
            self._image_crop = int(device_info.get(ATTR_CROP))
        else:
            self._image_crop = 0
        self._trim_up = device_info.get(ATTR_TRIM_TOP)
        if self._trim_up:
            self._trim_up = int(device_info.get(ATTR_TRIM_TOP))
        else:
            self._trim_up = 0
        self._trim_down = device_info.get(ATTR_TRIM_BOTTOM)
        if self._trim_down:
            self._trim_do = int(device_info.get(ATTR_TRIM_BOTTOM))
        else:
            self._trim_down = 0
        self._trim_left = device_info.get(ATTR_TRIM_LEFT)
        if self._trim_down:
            self._trim_do = int(device_info.get(ATTR_TRIM_LEFT))
        else:
            self._trim_left = 0
        self._trim_right = device_info.get(ATTR_TRIM_RIGHT)
        if self._trim_down:
            self._trim_do = int(device_info.get(ATTR_TRIM_RIGHT))
        else:
            self._trim_right = 0
        self._image = self.update()
        self._snapshot_taken = False
        self._show_vacuum_state = device_info.get(CONF_VAC_STAT)
        if not self._show_vacuum_state:
            self._show_vacuum_state = False
        self._last_image = None
        self._image_grab = True
        self._frame_nuber = 0
        self.throttled_camera_image = Throttle(timedelta(seconds=5))(self.camera_image)
        self._should_poll = True
        try:
            self.user_colors = [
                device_info.get(COLOR_WALL),
                device_info.get(COLOR_ZONE_CLEAN),
                device_info.get(COLOR_ROBOT),
                device_info.get(COLOR_BACKGROUND),
                device_info.get(COLOR_MOVE),
                device_info.get(COLOR_CHARGER),
                device_info.get(COLOR_NO_GO),
                device_info.get(COLOR_GO_TO),
                device_info.get(COLOR_TEXT),
            ]
            self.rooms_colors = [
                device_info.get(COLOR_ROOM_0),
                device_info.get(COLOR_ROOM_1),
                device_info.get(COLOR_ROOM_2),
                device_info.get(COLOR_ROOM_3),
                device_info.get(COLOR_ROOM_4),
                device_info.get(COLOR_ROOM_5),
                device_info.get(COLOR_ROOM_6),
                device_info.get(COLOR_ROOM_7),
                device_info.get(COLOR_ROOM_8),
                device_info.get(COLOR_ROOM_9),
                device_info.get(COLOR_ROOM_10),
                device_info.get(COLOR_ROOM_11),
                device_info.get(COLOR_ROOM_12),
                device_info.get(COLOR_ROOM_13),
                device_info.get(COLOR_ROOM_14),
                device_info.get(COLOR_ROOM_15),
            ]
            self._vacuum_shared.update_user_colors(
                add_alpha_to_rgb(self.user_colors, base_colors_array)
            )
            self._vacuum_shared.update_rooms_colors(
                add_alpha_to_rgb(self.rooms_colors, rooms_color)
            )
        except (ValueError, IndexError, UnboundLocalError) as e:
            _LOGGER.error("Error while populating colors: %s", e)

    async def async_added_to_hass(self) -> None:
        self.async_schedule_update_ha_state(True)

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal from Home Assistant."""
        await super().async_will_remove_from_hass()

        # Stop the camera and perform any necessary cleanup tasks here
        self.turn_off()

    @property
    def frame_interval(self) -> float:
        return 1

    def camera_image(
            self, width: Optional[int] = None, height: Optional[int] = None
    ) -> Optional[bytes]:
        return self._image

    @property
    def name(self) -> str:
        return self._attr_name

    def turn_on(self):
        self._mqtt.client_start()
        self._should_poll = True

    def turn_off(self):
        self._mqtt.client_stop()
        self._should_poll = False

    @property
    def supported_features(self) -> int:
        return SUPPORT_ON_OFF

    @property
    def extra_state_attributes(self):
        if self._map_rooms is None:
            return {
                "vacuum_entity": self._vacuum_entity,
                "vacuum_status": self._vacuum_state,
                "listen_to": self._mqtt_listen_topic,
                "snapshot": "/local/snapshot_" + self.file_name + ".png",
                "json_data": self._vac_json_data,
                "vacuum_json_id": self._vac_json_id,
                "vacuum_position": self._current,
                "calibration_points": self._attr_calibration_points,
            }
        else:
            return {
                "vacuum_entity": self._vacuum_entity,
                "vacuum_status": self._vacuum_state,
                "listen_to": self._mqtt_listen_topic,
                "snapshot": "/local/snapshot_" + self.file_name + ".png",
                "json_data": self._vac_json_data,
                "vacuum_json_id": self._vac_json_id,
                "vacuum_position": self._current,
                "calibration_points": self._attr_calibration_points,
                "rooms": self._map_rooms,
            }

    @property
    def should_poll(self) -> bool:
        return self._should_poll

    def empty_if_no_data(self):
        # Check if the snapshot file exists
        if os.path.isfile(self.snapshot_img) and (self._last_image is None):
            # Load the snapshot image
            self._last_image = Image.open(self.snapshot_img)
            _LOGGER.info(self.file_name + ": Snapshot image loaded")
            return self._last_image
        elif self._last_image is not None:
            return self._last_image
        else:
            # Create an empty image with a gray background
            empty_img = Image.new("RGB", (800, 600), "gray")
            _LOGGER.info(self.file_name + ": Staring up ...")
            return empty_img

    def take_snapshot(self, json_data, image_data):
        try:
            self._snapshot_taken = True
            # When logger is active.
            if _LOGGER.getEffectiveLevel() is not 0:
                # Save mqtt raw data file.
                if self._mqtt is not None:
                    self._mqtt.save_payload(self.file_name)
                # Write the JSON data to the file.
                with open(
                        "custom_components/valetudo_vacuum_camera/snapshots/"
                        + self.file_name
                        + ".json",
                        "w",
                ) as file:
                    json_data = json.dumps(json_data, indent=4)
                    file.write(json_data)
            # Save image ready for snapshot.
            image_data.save(self.snapshot_img)
            _LOGGER.info(self.file_name + ": Camera Snapshot Taken.")
        except IOError:
            self._snapshot_taken = None
            _LOGGER.warning(
                "Error Saving"
                + self.file_name
                + ": Snapshot, no snapshot available till restart."
            )
        else:
            _LOGGER.debug(
                self.file_name + ": Snapshot acquired during %s",
                {self._vacuum_state},
                " Vacuum State.",
                )

    def update(self):
        # check and update the vacuum reported state
        if self._mqtt:
            self._vacuum_state = self._mqtt.get_vacuum_status()
        # If we have data from MQTT, we process the image
        process_data = self._mqtt.is_data_available()
        if process_data:
            # if the vacuum is working, or it is the first image.
            if (
                    self._vacuum_state == "cleaning"
                    or self._vacuum_state == "moving"
                    or self._vacuum_state == "returning"
            ):
                # grab the image
                self._image_grab = True
                self._frame_nuber = self._map_handler.get_frame_number()
                # when the vacuum goes / is in idle, error or docked
                # take the snapshot.
                self._snapshot_taken = False
            # Starting the image processing.
            _LOGGER.info(
                self.file_name + ": Camera image data update available: %s",
                process_data,
                )
            start_time = datetime.now()
            try:
                # bypassed code is for debug purpose only
                #########################################################
                parsed_json = self._mqtt.update_data(self._image_grab)
                #########################################################
                # json_file = "custom_components/valetudo_vacuum_camera/snapshots/json_v2.json"
                # with open(json_file, "rb") as j_file:
                #    tmp_json = j_file.read()
                # parsed_json = json.loads(tmp_json)
                self._vac_json_data = "Success"
            except ValueError:
                self._vac_json_data = "Error"
                pass
            else:
                # Just in case, let's check that the data is available
                if parsed_json is not None:
                    self._map_rooms = self._map_handler.get_rooms_attributes()
                    pil_img = self._map_handler.get_image_from_json(
                        m_json=parsed_json,
                        robot_state=self._vacuum_state,
                        crop=self._image_crop,
                        trim_u=self._trim_up,
                        trim_b=self._trim_down,
                        trim_r=self._trim_right,
                        trim_l=self._trim_left,
                        user_colors=self._vacuum_shared.get_user_colors(),
                        rooms_colors=self._vacuum_shared.get_rooms_colors(),
                        file_name=self.file_name,
                    )
                    if pil_img is not None:
                        pil_img = pil_img.rotate(self._image_rotate)
                        _LOGGER.debug(
                            "Applied " + self.file_name + " image rotation: %s",
                            {self._image_rotate},
                            )
                        if self._show_vacuum_state:
                            self._map_handler.draw_status_text(
                                pil_img,
                                50,
                                self._vacuum_shared.user_colors[8],
                                self.file_name + ": " + self._vacuum_state
                            )
                        if not self._snapshot_taken and (
                                self._vacuum_state == "idle"
                                or self._vacuum_state == "docked"
                                or self._vacuum_state == "error"
                        ):
                            # suspend image processing if we are at the next frame.
                            if (
                                    self._frame_nuber
                                    is not self._map_handler.get_frame_number()
                            ):
                                self._image_grab = False
                                _LOGGER.info(
                                    "Suspended the camera data processing for: "
                                    + self.file_name
                                    + "."
                                )
                                # take a snapshot
                                self.take_snapshot(parsed_json, pil_img)
                        self._vac_json_id = self._map_handler.get_json_id()
                        self._base = self._map_handler.get_charger_position()
                        self._current = self._map_handler.get_robot_position()
                        self._vac_img_data = self._map_handler.get_img_size()
                        self._attr_calibration_points = (
                            self._map_handler.get_calibration_data(self._image_rotate)
                        )
                    else:
                        # if no image was processed empty or last snapshot/frame
                        pil_img = self.empty_if_no_data()
                    # Converting the image obtained to bytes
                    # Using openCV would reduce the CPU and memory usage.
                    # On Py4 HA OS is not possible to install the openCV library.
                    buffered = BytesIO()
                    # backup the image
                    self._last_image = pil_img
                    pil_img.save(buffered, format="PNG")
                    bytes_data = buffered.getvalue()
                    self._image = bytes_data
                    # clean up
                    del buffered, pil_img, bytes_data
                    _LOGGER.info(self.file_name + ": Image update complete")
                    processing_time = (datetime.now() - start_time).total_seconds()
                    self._frame_interval = max(0.1, processing_time)
                    _LOGGER.debug(
                        "Adjusted " + self.file_name + ": Frame interval: %s",
                        self._frame_interval,
                        )
                else:
                    _LOGGER.info(
                        self.file_name
                        + ": Image not processed. Returning not updated image."
                    )
                    self._frame_interval = 0.1
                return self._image

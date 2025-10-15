"""
Camera
Last Updated on version: 2025.10.0
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from io import BytesIO
import math
import os
import time
from typing import Optional

from homeassistant import config_entries, core
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.const import CONF_UNIQUE_ID, MATCH_ALL
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo as Dev_Info
from homeassistant.helpers.entity import DeviceInfo as Entity_Info
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from valetudo_map_parser.config.colors import ColorsManagement
from valetudo_map_parser.config.utils import ResizeParams, async_resize_image

from .common import get_vacuum_unique_id_from_mqtt_topic
from .const import (
    ATTR_FRIENDLY_NAME,
    ATTR_VACUUM_TOPIC,
    CAMERA_SCAN_INTERVAL_S,
    CAMERA_STORAGE,
    CONF_VACUUM_IDENTIFIERS,
    DOMAIN,
    DOWNLOAD_TIMEOUT,
    FRAME_INTERVAL_S,
    LOGGER,
    RENDER_TIMEOUT_S,
    CameraModes,
)
from .utils.camera.camera_processing import CameraProcessor
from .utils.connection.decompress import DecompressionManager
from .utils.files_operations import async_load_file
from .utils.thread_pool import ThreadPoolManager

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SCAN_INTERVAL = timedelta(seconds=CAMERA_SCAN_INTERVAL_S)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
) -> None:
    """Setup camera from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    # Update our config to and eventually add or remove option.
    if config_entry.options:
        config.update(config_entry.options)

    camera = [MQTTCamera(coordinator, config)]
    async_add_entities(camera, update_before_add=True)


class MQTTCamera(CoordinatorEntity, Camera):
    """
    Rend the vacuum map and the vacuum state for:
    Valetudo Hypfer and rand256 Firmwares Vacuums maps.
    From PI4 up to all other Home Assistant supported platforms.
    """

    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset({MATCH_ALL})

    # noinspection PyUnusedLocal
    def __init__(self, coordinator, device_info):
        super().__init__(coordinator)
        Camera.__init__(self)
        self.hass = coordinator.hass
        self._shared = coordinator.shared
        self._file_name = coordinator.file_name
        self._attr_model = "MQTT Vacuums"
        self._attr_brand = "MQTT Vacuum Camera"
        self._attr_name = "Camera"
        self._attr_is_on = True
        self._homeassistant_path = self.hass.config.path()  # get Home Assistant path
        self._storage_path, self.log_file = self._init_paths()
        self._mqtt_listen_topic = coordinator.vacuum_topic
        self._attr_unique_id = device_info.get(
            CONF_UNIQUE_ID,
            get_vacuum_unique_id_from_mqtt_topic(self._mqtt_listen_topic),
        )
        self._mqtt = coordinator.connector
        self._identifiers = device_info.get(CONF_VACUUM_IDENTIFIERS)
        self.Image = None
        self._image_bk = None
        self._processing = False
        self._image_w = None
        self._image_h = None
        self._should_poll = False
        self._attr_frame_interval = float(timedelta(seconds=6).total_seconds())
        self._json_data = None
        self._init_clear_www_folder()
        self._last_image = None
        self._obstacle_image = None
        # Set default language to English - only set once during initialization
        self._shared.user_language = "en"
        # get the colours used in the maps.
        self._colours = ColorsManagement(self._shared)
        self._colours.set_initial_colours(device_info)
        self.thread_pool = ThreadPoolManager.get_instance(self._file_name)
        # Create the processor for the camera.
        self.processor = CameraProcessor(self.hass, self._shared, self.thread_pool)
        self._shared.image_grab = True
        self._dm = DecompressionManager.get_instance(self._file_name)
        # Listen to the vacuum.start event
        self.uns_event_vacuum_start = self.hass.bus.async_listen(
            "event_vacuum_start", self.handle_vacuum_start
        )
        # Initialize debouncer for obstacle view events
        self._obstacle_view_debouncer = Debouncer(
            self.hass,
            LOGGER,
            cooldown=0.5,  # 500ms debounce for rapid events
            immediate=True,  # Process first event immediately
            function=self._process_obstacle_event,
        )

        self.uns_event_obstacle_coordinates = self.hass.bus.async_listen(
            "mqtt_vacuum_camera_obstacle_coordinates", self._debounced_obstacle_handler
        )

    def _init_clear_www_folder(self):
        """Remove PNG and ZIP's stored in HA config WWW"""
        # If enable_snapshots check if for png in www
        if not self._shared.enable_snapshots and os.path.isfile(
            f"{self._homeassistant_path}/www/snapshot_{self._file_name}.png"
        ):
            os.remove(f"{self._homeassistant_path}/www/snapshot_{self._file_name}.png")
        # If there is a log zip in www remove it
        if os.path.isfile(self.log_file):
            os.remove(self.log_file)

    def _init_paths(self):
        """Initialize Camera Paths"""
        storage_path = f"{self.hass.config.path(STORAGE_DIR)}/{CAMERA_STORAGE}"
        if not os.path.exists(storage_path):
            storage_path = f"{self._homeassistant_path}/{STORAGE_DIR}"
        log_file = f"{storage_path}/{self._file_name}.zip"
        return storage_path, log_file

    async def async_cleanup_all(self):
        """Clean up all dispatcher connections."""
        # Clean up coordinator's own dispatchers
        if self.uns_event_vacuum_start:
            self.uns_event_vacuum_start()
        if self.uns_event_obstacle_coordinates:
            self.uns_event_obstacle_coordinates()
        if self._obstacle_view_debouncer:
            self._obstacle_view_debouncer.async_shutdown()

    async def async_added_to_hass(self) -> None:
        """Handle entity added to Home Assistant."""
        self._should_poll = True
        _start_image = self._shared.last_image
        self.Image = await self.hass.async_add_executor_job(
            self.pil_to_bytes, _start_image, "Start Up"
        )
        self._shared.camera_mode = CameraModes.MAP_VIEW
        self.async_schedule_update_ha_state(True)

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal from Home Assistant."""
        await super().async_will_remove_from_hass()
        await self.async_cleanup_all()

        # Unsubscribe from MQTT topics
        if self._mqtt:
            await self._mqtt.async_unsubscribe_from_topics()

        # Shutdown thread pool for this camera instance only
        if hasattr(self, "thread_pool") and self.thread_pool:
            await self.thread_pool.shutdown_instance()
            LOGGER.debug("Thread pool for camera %s shut down", self._file_name)

        LOGGER.debug("Camera entity removed from HA for: %s", self._file_name)

    @property
    def name(self) -> str:
        """Camera Entity Name"""
        return self._attr_name

    @property
    def model(self) -> str | None:
        """Return the camera model."""
        return self._attr_model

    @property
    def brand(self) -> str | None:
        """Return the camera brand."""
        return self._attr_brand

    @property
    def is_on(self) -> bool:
        """Return true if on."""
        return self._attr_is_on

    @property
    def frame_interval(self) -> float:
        """Camera Frame Interval"""
        return self._attr_frame_interval

    @property
    def is_streaming(self) -> bool:
        """Return true if the device is streaming."""
        if self.processor.data:
            self._attr_is_streaming = self.processor.data["image"]["streaming"]
        else:
            self._attr_is_streaming = True
        return self._attr_is_streaming

    def disable_motion_detection(self) -> bool:
        """Disable Motion Detection
        :return bool always False as this is not in use in this implementation"""
        return False

    def enable_motion_detection(self) -> bool:
        """Enable Motion Detection
        :return bool always False as this is not in use in this implementation"""
        return False

    # noinspection PyUnusedLocal
    def camera_image(
        self, width: Optional[int] = None, height: Optional[int] = None
    ) -> Optional[bytes]:
        """Camera Image"""
        if self._shared.binary_image is None:
            return self.Image
        width, height = self.processor.data["image"]["size"]
        return self.processor.data["image"]["binary"]

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return CameraEntityFeature.ON_OFF

    @property
    def extra_state_attributes(self) -> dict:
        """Return Camera Attributes"""
        attr_data = self._shared.to_dict()["attributes"]
        attributes = {
            ATTR_FRIENDLY_NAME: self._attr_name,
            ATTR_VACUUM_TOPIC: self._mqtt_listen_topic,
        }
        attributes.update(attr_data)
        return attributes

    @property
    def should_poll(self) -> bool:
        """ON/OFF Camera Polling Based on Camera Mode."""
        poling_states = {
            CameraModes.OBSTACLE_DOWNLOAD: False,
            CameraModes.OBSTACLE_SEARCH: False,
            CameraModes.MAP_VIEW: True,
            CameraModes.OBSTACLE_VIEW: True,
            CameraModes.CAMERA_STANDBY: False,
        }

        if isinstance(self._shared.camera_mode, bool):
            self._shared.camera_mode = (
                CameraModes.MAP_VIEW
                if self._shared.camera_mode
                else CameraModes.CAMERA_STANDBY
            )

        self._should_poll = poling_states.get(self._shared.camera_mode, False)
        return self._should_poll

    @property
    def device_info(self):
        """Return the device info."""
        device_info = Dev_Info if Dev_Info else Entity_Info
        return device_info(identifiers=self._identifiers)

    def turn_on(self) -> None:
        """Camera Turn On"""
        self._shared.camera_mode = CameraModes.CAMERA_ON

    def turn_off(self) -> None:
        """Camera Turn Off"""
        self._shared.camera_mode = CameraModes.CAMERA_OFF

    async def _update_vacuum_state(self) -> str:
        """Update a few shared fields; light-weight."""
        self._shared.vacuum_battery = await self._mqtt.get_battery_level()
        self._shared.vacuum_connection = await self._mqtt.get_vacuum_connection_state()

        if not self._shared.vacuum_connection:
            self._shared.vacuum_state = "disconnected"
        else:
            self._shared.vacuum_state = await self._mqtt.get_vacuum_status()
        return self._shared.vacuum_state

    async def async_update(self):
        """Camera Frame Update."""

        # Obstacle View Processing
        if self._shared.camera_mode == CameraModes.OBSTACLE_VIEW:
            if self._obstacle_image is not None:
                self.Image = (
                    self._obstacle_image
                )  # this must be set for the camera_image() to work.
                return self._obstacle_image

        if self._shared.camera_mode == CameraModes.MAP_VIEW:
            # if the vacuum is working, or it is the first image.

            _ = await self._update_vacuum_state()
            if _ != "docked" or self.is_streaming:
                self._shared.image_grab = True
                self._shared.frame_number = self.processor.get_frame_number()
                # Record the time when we receive image data
                self._attr_frame_interval = FRAME_INTERVAL_S

            parsed_json, is_a_test, data_type = await self._process_parsed_json()

            if parsed_json is not None:
                if not self._shared.destinations and data_type == "Rand256":
                    self._shared.destinations = self._mqtt.get_destinations()
                try:
                    await asyncio.wait_for(
                        self.processor.run_process_valetudo_data(parsed_json),
                        timeout=RENDER_TIMEOUT_S,
                    )
                except asyncio.TimeoutError:
                    LOGGER.warning("%s: Time out in redering!", self._file_name)
                    return self.camera_image(self._image_w, self._image_h)
        return self.camera_image(self._image_w, self._image_h)

    async def _process_parsed_json(self, test_mode: bool = False):
        """Process the parsed JSON data and return the generated image."""
        if test_mode:
            LOGGER.debug("Camera Test Mode Active...")
            data_type = "hypfer"
            if not self._shared.image_grab:
                return None, test_mode, data_type
            if self._json_data is None:
                self._json_data = await async_load_file(
                    file_to_load="custom_components/mqtt_vacuum_camera/snapshots/test.json",
                    is_json=True,
                )
            parsed_json = self._json_data
            self._shared.camera_mode = CameraModes.MAP_VIEW
            return parsed_json, test_mode, data_type

        # Get data from MQTT and decompress it
        parsed_json = None
        payload, data_type = await self._mqtt.update_data(self._shared.image_grab)
        if payload and data_type:
            data = payload.payload if hasattr(payload, "payload") else payload
            parsed_json = await self.hass.async_create_task(
                self._dm.decompress(self._file_name, data, data_type)
            )
        return parsed_json, test_mode, data_type

    def pil_to_bytes(self, pil_img, image_id: str = None) -> Optional[bytes]:
        """Convert PIL image to bytes"""
        if pil_img:
            LOGGER.debug(
                "%s: Output Image: %s.",
                self._file_name,
                image_id if image_id else self._shared.vac_json_id,
            )
        else:
            if self._last_image is not None:
                LOGGER.debug("%s: Output Last Image.", self._file_name)
                pil_img = self._shared.last_image
        self._image_w = pil_img.width
        self._image_h = pil_img.height
        buffered = BytesIO()
        try:
            pil_img.save(buffered, format="PNG")
            return buffered.getvalue()
        finally:
            buffered.close()

    async def run_async_pil_to_bytes(self, pil_img, image_id: str = None):
        """Thread function to process the image data using persistent thread pool."""
        try:
            result = await self.thread_pool.run_in_executor(
                "camera_processing",
                self.pil_to_bytes,
                pil_img,
                image_id,
            )
            return result
        except Exception as e:
            LOGGER.error("Error converting image to bytes: %s", str(e), exc_info=True)
            return None

    async def handle_vacuum_start(self, event):
        """Handle the event_vacuum_start event."""
        self._shared.reset_trims()  # requires valetudo_map_parser >0.1.9b41

    async def _debounced_obstacle_handler(self, event):
        """Handler that debounced incoming obstacle view events."""
        # Store the latest event data
        self._latest_obstacle_event = event
        # Trigger the debouncer - it will call _process_obstacle_event after cooldown
        await self._obstacle_view_debouncer.async_call()

    async def _process_obstacle_event(self):
        """Process the latest obstacle event after debouncing."""
        if not hasattr(self, "_latest_obstacle_event"):
            return

        event = self._latest_obstacle_event
        await self.handle_obstacle_view(event)

    async def handle_obstacle_view(self, event):
        """Handle the event mqtt_vacuum_camera_obstacle_coordinates."""
        width = self._shared.image_ref_width
        height = self._shared.image_ref_height
        shared_ratio = self._shared.image_aspect_ratio
        obstacles_data = self._shared.obstacles_data

        async def _set_map_view_mode(reason: str = None):
            """Set the camera mode to MAP_VIEW."""
            self._shared.camera_mode = CameraModes.MAP_VIEW
            LOGGER.debug(
                "%s: Camera Mode Change to %s%s",  # ruff: noqa: E501
                self._file_name,
                self._shared.camera_mode,
                f", {reason}" if reason else "",
            )
            if self._image_bk:
                self.Image = self._image_bk
                return self.camera_image(self._image_w, self._image_h)
            return self.Image

        async def _set_camera_mode(mode_of_camera: CameraModes, reason: str = None):
            """Set the camera mode."""
            self._shared.camera_mode = mode_of_camera

            match mode_of_camera:
                case CameraModes.OBSTACLE_SEARCH:
                    if not self._image_bk:
                        self._image_bk = self.Image

                case CameraModes.OBSTACLE_VIEW:
                    self._shared.image_grab = False
                    self._processing = True

                case CameraModes.MAP_VIEW:
                    self._obstacle_image = None
                    self._processing = False
                    self._shared.image_grab = True
                    if self._image_bk:
                        self.Image = self._image_bk
                        self._image_bk = None
                        self.camera_image(self._image_w, self._image_h)
            LOGGER.debug(
                "%s: Camera Mode Change to %s%s",  # ruff: noqa: E501
                self._file_name,
                self._shared.camera_mode,
                f", {reason}" if reason else "",
            )

        async def _async_find_nearest_obstacle(x, y, all_obstacles):
            """Find the nearest obstacle to the given coordinates."""
            nearest_obstacles = None
            w = width
            h = height
            min_distance = round(65 * (w / h))
            LOGGER.debug(
                "Finding in the nearest %d pixels obstacle to coordinates: %d, %d",
                min_distance,
                x,
                y,
            )

            for obstacle in all_obstacles:
                obstacle_point = obstacle["point"]
                obstacle_x = obstacle_point["x"]
                obstacle_y = obstacle_point["y"]

                # Calculate Euclidean distance
                distance = math.sqrt((x - obstacle_x) ** 2 + (y - obstacle_y) ** 2)

                if distance < min_distance:
                    min_distance = distance
                    nearest_obstacles = obstacle

            return nearest_obstacles

        LOGGER.debug(
            "%s: Executing obstacle view logic for event: %s, Data: %s",
            self._file_name,
            str(event.event_type),
            str(event.data),
        )
        # Check if we are in obstacle view and switch back to map view
        LOGGER.debug(
            "%s: Current camera mode: %s",
            self._file_name,
            self._shared.camera_mode,
        )

        if self._shared.camera_mode == CameraModes.OBSTACLE_VIEW:
            return await _set_map_view_mode("Obstacle View Exit Requested.")

        # Prevent processing if already in obstacle processing modes
        if self._shared.camera_mode in [
            CameraModes.OBSTACLE_DOWNLOAD,
            CameraModes.OBSTACLE_SEARCH,
        ]:
            LOGGER.debug(
                "%s: Already processing obstacle view (mode: %s), ignoring request",
                self._file_name,
                self._shared.camera_mode,
            )
            return self.Image

        if obstacles_data and self._shared.camera_mode == CameraModes.MAP_VIEW:
            if event.data.get("entity_id") != self.entity_id:
                return await _set_camera_mode(
                    CameraModes.MAP_VIEW, "Entity ID mismatch"
                )
            await _set_camera_mode(
                CameraModes.OBSTACLE_SEARCH, "Obstacle View Requested"
            )
            coordinates = event.data.get("coordinates", None)
            if coordinates:
                obstacles = obstacles_data
                coordinates_x = coordinates.get("x")
                coordinates_y = coordinates.get("y")
                # Find the nearest obstacle
                nearest_obstacle = await _async_find_nearest_obstacle(
                    coordinates_x, coordinates_y, obstacles
                )
                if nearest_obstacle:
                    LOGGER.debug(
                        "%s: Nearest obstacle found: %r",
                        self._file_name,
                        nearest_obstacle,
                    )
                    if not nearest_obstacle["link"]:
                        return await _set_map_view_mode(
                            "No link found for the obstacle image."
                        )

                    await _set_camera_mode(
                        mode_of_camera=CameraModes.OBSTACLE_DOWNLOAD,
                        reason=f"Downloading image: {nearest_obstacle['link']}",
                    )

                    # Download the image
                    try:
                        image_data = await asyncio.wait_for(
                            fut=self.processor.download_image(
                                nearest_obstacle["link"], DOWNLOAD_TIMEOUT
                            ),
                            timeout=(
                                DOWNLOAD_TIMEOUT + 1
                            ),  # dead man switch, do not remove.
                        )
                    except asyncio.TimeoutError:
                        LOGGER.warning("%s: Image download timed out.", self._file_name)
                        return await _set_map_view_mode(
                            "Obstacle image download timed out."
                        )

                    # Process the image if download was successful
                    if image_data is not None:
                        await _set_camera_mode(
                            CameraModes.OBSTACLE_VIEW, "Image downloaded successfully"
                        )
                        try:
                            start_time = time.perf_counter()
                            # Open the downloaded image with PIL
                            pil_img = await self.processor.async_open_image(image_data)
                            # Resize the image if resize_to is provided
                            if shared_ratio != "None":
                                resize_data = ResizeParams(
                                    pil_img=pil_img,
                                    width=width,
                                    height=height,
                                    aspect_ratio=shared_ratio,
                                    crop_size=[],
                                    is_rand=False,
                                    offset_func=None,
                                )
                                # Handle the case where async_resize_image returns an Image object instead of a tuple
                                resize_result = await async_resize_image(
                                    params=resize_data
                                )
                                if isinstance(resize_result, tuple):
                                    resized_image, _ = resize_result
                                else:
                                    # If it's not a tuple, assume it's the image directly
                                    resized_image = resize_result

                                # Use the resized image
                                image = resized_image
                            else:
                                # Use original image if no aspect ratio is set
                                image = pil_img
                            self._obstacle_image = await self.run_async_pil_to_bytes(
                                image,
                                image_id=nearest_obstacle["label"],
                            )
                            end_time = time.perf_counter()
                            LOGGER.debug(
                                "%s: Image processing time: %r seconds",
                                self._file_name,
                                end_time - start_time,
                            )
                            self.Image = self._obstacle_image
                            self.async_schedule_update_ha_state(force_refresh=True)
                            return self._obstacle_image
                        except HomeAssistantError as e:
                            LOGGER.warning(
                                "%s: Unexpected Error processing image: %r",
                                self._file_name,
                                e,
                                exc_info=True,
                            )
                            return await _set_map_view_mode("Error processing image")
                    else:
                        return await _set_map_view_mode("No image downloaded.")
                return await _set_map_view_mode("No nearby obstacle found.")
            return await _set_map_view_mode("No coordinates provided.")
        else:
            return await _set_map_view_mode("No obstacles data available.")

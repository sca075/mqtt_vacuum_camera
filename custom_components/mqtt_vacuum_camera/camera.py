"""
Camera
Last Updated on version: 2025.5.0
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from io import BytesIO
import math
import os
import platform
import time
from typing import Any, Optional

from PIL import Image
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
from psutil_home_assistant import PsutilWrapper as ProcInspector
from valetudo_map_parser.config.colors import ColorsManagement
from valetudo_map_parser.config.types import SnapshotStore
from valetudo_map_parser.config.utils import ResizeParams, async_resize_image

from .common import get_vacuum_unique_id_from_mqtt_topic
from .const import (
    ATTR_FRIENDLY_NAME,
    ATTR_JSON_DATA,
    ATTR_SNAPSHOT_PATH,
    ATTR_VACUUM_TOPIC,
    CAMERA_STORAGE,
    CONF_VACUUM_IDENTIFIERS,
    DOMAIN,
    DOWNLOAD_TIMEOUT,
    LOGGER,
    NOT_STREAMING_STATES,
    CameraModes,
)
from .snapshots.snapshot import Snapshots
from .utils.camera.camera_processing import CameraProcessor
from .utils.connection.decompress import DecompressionManager
from .utils.files_operations import async_load_file
from .utils.thread_pool import ThreadPoolManager

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SCAN_INTERVAL = timedelta(seconds=3)


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
        self._shared, self._file_name = coordinator.update_shared_data(device_info)
        self._state = "init"
        self._attr_model = "MQTT Vacuums"
        self._attr_brand = "MQTT Vacuum Camera"
        self._attr_name = "Camera"
        self._attr_is_on = True
        self._attr_motion_detection_enabled = False
        self._homeassistant_path = self.hass.config.path()  # get Home Assistant path
        self._start_up_logs()
        self._storage_path, self.snapshot_img, self.log_file = self._init_paths()
        self._mqtt_listen_topic = coordinator.vacuum_topic
        self._attr_unique_id = device_info.get(
            CONF_UNIQUE_ID,
            get_vacuum_unique_id_from_mqtt_topic(self._mqtt_listen_topic),
        )
        self._mqtt = coordinator.connector
        self._identifiers = device_info.get(CONF_VACUUM_IDENTIFIERS)
        self._snapshots = Snapshots(self.hass, self._shared)
        self.Image = None
        self._image_bk = None
        self._processing = False
        self._image_w = None
        self._image_h = None
        self._should_poll = False
        self._attr_frame_interval = 6
        self._json_data = None
        self._vac_json_available = None
        self._cpu_percent = None
        self._init_clear_www_folder()
        self._last_image = None
        self._obstacle_image = None
        self.auth_update_time = None
        self._dm = DecompressionManager.get_instance(self._file_name)
        LOGGER.debug(
            "%s: Initialized DecompressionManager for this vacuum", self._file_name
        )
        self._image_receive_time = None  # Timestamp when image data is received
        # Set default language to English - only set once during initialization
        self._shared.user_language = "en"
        # get the colours used in the maps.
        self._colours = ColorsManagement(self._shared)
        self._colours.set_initial_colours(device_info)
        # Create the processor for the camera.
        self.processor = CameraProcessor(self.hass, self._shared)
        self.thread_pool = ThreadPoolManager(self._file_name)
        self._shared.image_grab = True
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

    @staticmethod
    def _start_up_logs():
        """Logs the machine running the component data"""
        LOGGER.debug("System Release: %r, %r", platform.node(), platform.release())
        LOGGER.debug("System Version: %r", platform.version())
        LOGGER.debug("System Machine: %r", platform.machine())
        LOGGER.debug("Python Version: %r", platform.python_version())
        LOGGER.debug(
            "Memory Available: %r and In Use: %r",
            round(
                (ProcInspector().psutil.virtual_memory().available / (1024 * 1024)), 1
            ),
            round((ProcInspector().psutil.virtual_memory().used / (1024 * 1024)), 1),
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
        snapshot_img = f"{storage_path}/{self._file_name}.png"
        log_file = f"{storage_path}/{self._file_name}.zip"
        return storage_path, snapshot_img, log_file

    async def async_added_to_hass(self) -> None:
        """Handle entity added to Home Assistant."""
        await self._mqtt.async_subscribe_to_topics()
        self._should_poll = True
        self._shared.camera_mode = CameraModes.MAP_VIEW
        self.async_schedule_update_ha_state(True)

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal from Home Assistant."""
        await super().async_will_remove_from_hass()

        # Unsubscribe from MQTT topics
        if self._mqtt:
            await self._mqtt.async_unsubscribe_from_topics()

        # Shutdown the snapshot thread pool
        if hasattr(self, "_snapshots") and self._snapshots:
            await self._snapshots.shutdown()

        # Shutdown the DecompressionManager for this vacuum
        if hasattr(self, "_dm") and self._dm:
            LOGGER.debug(
                "%s: Shutting down DecompressionManager during entity removal",
                self._file_name,
            )
            await self._dm.shutdown()

        # Shutdown camera thread pools
        await self.thread_pool.shutdown(self._file_name)

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
        updated_status = self._shared.vacuum_state
        self._attr_is_streaming = (
            updated_status not in NOT_STREAMING_STATES
            or not self._shared.vacuum_bat_charged
        )
        return self._attr_is_streaming

    def disable_motion_detection(self) -> bool:
        """Disable Motion Detection
        :return bool always False as this is not in use in this implementation"""
        return False

    def enable_motion_detection(self) -> bool:
        """Enable Motion Detection
        :return bool always False as this is not in use in this implementation"""
        return False

    def camera_image(
        self, width: Optional[int] = None, height: Optional[int] = None
    ) -> Optional[bytes]:
        """Camera Image"""
        return self.Image

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return CameraEntityFeature.ON_OFF

    @property
    def extra_state_attributes(self) -> dict:
        """Return Camera Attributes"""
        attributes = {
            ATTR_FRIENDLY_NAME: self._attr_name,
            ATTR_VACUUM_TOPIC: self._mqtt_listen_topic,
            ATTR_JSON_DATA: self._vac_json_available,
            ATTR_SNAPSHOT_PATH: f"/local/snapshot_{self._file_name}.png",
        }
        attributes.update(self._shared.generate_attributes())
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

    @staticmethod
    def _load_snapshot_image(snapshot_path: str) -> Image.Image:
        """
        Synchronous helper function to load snapshot image from file.
        This function is designed to be called from a thread pool.
        """
        return Image.open(snapshot_path)

    async def async_empty_if_no_data(self) -> Image:
        """
        It will return the last image if available or
        an empty image if there are no data.
        This is the async version that uses thread pool for file I/O.
        """
        if self._last_image:
            LOGGER.debug("%s: Returning Last image.", self._file_name)
            return self._last_image
        # Check if the snapshot file exists
        LOGGER.info("%s: Searching for %s.", self._file_name, self.snapshot_img)
        if os.path.isfile(self.snapshot_img):
            try:
                # Load the snapshot image using thread pool to avoid blocking
                self._last_image = await self.thread_pool.run_in_executor(
                    "snapshot", self._load_snapshot_image, self.snapshot_img
                )
                LOGGER.debug("%s: Returning Snapshot image.", self._file_name)
                return self._last_image
            except Exception as e:
                LOGGER.warning(
                    "%s: Error loading snapshot image %s: %s",
                    self._file_name,
                    self.snapshot_img,
                    str(e),
                )
                # Fall through to create empty image
        # Create an empty image with a gray background
        empty_img = Image.new("RGB", (800, 600), "gray")
        LOGGER.info("%s: Returning Empty image.", self._file_name)
        return empty_img

    def empty_if_no_data(self) -> Image:
        """
        Deprecated synchronous version - kept for backward compatibility.
        Use async_empty_if_no_data() instead.
        """
        LOGGER.warning(
            "%s: Using deprecated synchronous empty_if_no_data(). "
            "Consider using async_empty_if_no_data() instead.",
            self._file_name,
        )
        if self._last_image:
            LOGGER.debug("%s: Returning Last image.", self._file_name)
            return self._last_image
        # Create an empty image with a gray background without file I/O
        empty_img = Image.new("RGB", (800, 600), "gray")
        LOGGER.info("%s: Returning Empty image (no file loading).", self._file_name)
        return empty_img

    async def take_snapshot(self, json_data: Any, image_data: Image.Image) -> None:
        """Camera Automatic Snapshots."""
        partial_snapshot = SnapshotStore()
        await partial_snapshot.async_set_snapshot_save_data(self._file_name)
        await self._snapshots.run_async_take_snapshot(json_data, image_data)

    async def async_update(self):
        """Camera Frame Update."""

        # Obstacle View Processing
        if self._shared.camera_mode == CameraModes.OBSTACLE_VIEW:
            if self._obstacle_image is not None:
                self.Image = self._obstacle_image # this must be set for the camera_image() to work.
                return self._obstacle_image

        # Map View Processing
        if not self._mqtt:
            LOGGER.debug("%s: No MQTT data available.", self._file_name)
            # return last/empty image if no MQTT or CPU usage too high.
            await self._handle_no_mqtt_data()

        # If we have data from MQTT, we process the image.
        await self._update_vacuum_state()
        pid = os.getpid()  # Start to log the CPU usage of this PID.
        proc = ProcInspector().psutil.Process(pid)  # Get the process PID.
        process_data = await self._mqtt.is_data_available()
        if process_data and (self._shared.camera_mode == CameraModes.MAP_VIEW):
            # to calculate the cycle time for frame adjustment.
            start_time = time.perf_counter()
            self._log_cpu_usage(proc)
            # if the vacuum is working, or it is the first image.
            if self.is_streaming:
                self._shared.image_grab = True
                self._shared.snapshot_take = False
                self._shared.frame_number = self.processor.get_frame_number()
            # Record the time when we receive image data
            self._image_receive_time = time.time()
            self._processing = True
            parsed_json = None
            data_type = None
            is_a_test = False
            try:
                # Process the parsed JSON data
                parsed_json, is_a_test, data_type = await self._process_parsed_json()
            except ValueError:
                self._vac_json_available = "Error"
                pil_img = await self.async_empty_if_no_data()
                self.Image = await self.run_async_pil_to_bytes(pil_img)
                s = self.camera_image(self._image_w, self._image_h)
                return s
            finally:
                # Just in case, let's check that the data is available.
                if parsed_json is not None:
                    if not self._shared.destinations and data_type == "Rand256":
                        self._shared.destinations = await self._mqtt.get_destinations()

                    pil_img = await self.hass.async_create_task(
                        self.processor.run_async_process_valetudo_data(parsed_json)
                    )

                    # if no image was processed empty or last snapshot/frame
                    if not is_a_test and pil_img is None:
                        pil_img = await self.async_empty_if_no_data()

                    # update the image
                    self._last_image = pil_img.copy()
                    self.Image = await self.run_async_pil_to_bytes(pil_img)

                    if (
                        self._shared.vacuum_state == "docked"
                        and self._shared.camera_mode == CameraModes.MAP_VIEW
                    ):
                        self._image_bk = self.Image
                    elif (
                        self._shared.camera_mode == CameraModes.MAP_VIEW
                        and self._shared.vacuum_state != "docked"
                    ):
                        self._image_bk = None
                    await self._take_snapshot(parsed_json, pil_img)

                    # Update frame interval based on total processing time if we have a received timestamp
                    if self._image_receive_time is not None:
                        self._update_frame_interval_from_receive_time(
                            self._image_receive_time
                        )
                        self._image_receive_time = None  # Reset for next cycle
                    else:
                        # Fall back to old method if no receive timestamp
                        self._update_frame_interval(start_time)
                else:
                    LOGGER.info(
                        "%s: Image not processed. Returning not updated image.",
                        self._file_name,
                    )
                    self._attr_frame_interval = 0.1
                # HA supervised Memory and CUP usage report.
                self._log_memory_usage(proc)
                self._log_cpu_usage(proc)
                self._processing = False
        return self.camera_image(self._image_w, self._image_h)

    async def _update_vacuum_state(self):
        """Update vacuum state based on MQTT data."""
        self._shared.vacuum_battery = await self._mqtt.get_battery_level()
        self._shared.vacuum_connection = await self._mqtt.get_vacuum_connection_state()

        if not self._shared.vacuum_connection:
            self._shared.vacuum_state = "disconnected"
        else:
            if self._shared.vacuum_state == "disconnected":
                self._shared.vacuum_state = await self._mqtt.get_vacuum_status()
            else:
                self._shared.vacuum_state = await self._mqtt.get_vacuum_status()

    async def _handle_no_mqtt_data(self):
        """Handle the scenario where no MQTT data is available."""
        pil_img = await self.async_empty_if_no_data()
        self.Image = await self.run_async_pil_to_bytes(pil_img)
        return self.camera_image(pil_img.width, pil_img.height)

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
        LOGGER.debug(
            "%s: Check shared data. %s", self._file_name, self._shared.image_grab
        )
        payload, data_type = await self._mqtt.update_data(self._shared.image_grab)
        if payload and data_type:
            data = payload.payload if hasattr(payload, "payload") else payload
            parsed_json = await self.hass.async_create_task(
                self._dm.decompress(self._file_name, data, data_type)
            )

        if not parsed_json or not data_type:
            self._vac_json_available = "Error"
            empty_img = await self.async_empty_if_no_data()
            self.Image = await self.run_async_pil_to_bytes(empty_img)
            self.camera_image(self._image_w, self._image_h)
            LOGGER.warning(
                "%s: No JSON data available. Camera Suspended required reload.",
                self._file_name,
            )
            self._should_poll = False
            return None, False, None
        self._vac_json_available = "Success"
        if data_type == "Rand256":
            self._shared.is_rand = True
        else:
            self._shared.is_rand = False

        return parsed_json, test_mode, data_type

    async def _take_snapshot(self, parsed_json, pil_img):
        """Take a snapshot if conditions are met."""
        if self._shared.snapshot_take and pil_img:
            if self._shared.is_rand:
                await self.take_snapshot(self._shared.is_rand, pil_img)
            else:
                await self.take_snapshot(parsed_json, pil_img)

    def _log_cpu_usage(self, proc):
        """Log the CPU usage."""
        self._cpu_percent = round(
            ((proc.cpu_percent() / int(ProcInspector().psutil.cpu_count())) / 10), 1
        )

    def _log_memory_usage(self, proc):
        """Log the memory usage."""
        memory_percent = round(
            (
                (proc.memory_info()[0] / 2.0**30)
                / (ProcInspector().psutil.virtual_memory().total / 2.0**30)
            )
            * 100,
            2,
        )
        LOGGER.debug(
            "%s: Camera Memory: GB in use %.2f / system available %.2f%%.",
            self._file_name,
            round(proc.memory_info()[0] / 2.0**30, 2),
            memory_percent,
        )

    def _update_frame_interval(self, start_time):
        """Update the frame interval based on processing time."""
        processing_time = round((time.perf_counter() - start_time), 3)
        self._attr_frame_interval = max(0.1, processing_time)

    def _update_frame_interval_from_receive_time(self, receive_time):
        """Update the frame interval based on total time from receiving image data to completion."""
        total_time = round((time.time() - receive_time), 3)
        self._attr_frame_interval = max(0.1, total_time)

        LOGGER.debug(
            "%s: Image Completed - Total image processing time (receive to display): %.3fs",
            self._file_name,
            total_time,
        )

    async def async_pil_to_bytes(
        self, pil_img, image_id: str = None
    ) -> Optional[bytes]:
        """Convert PIL image to bytes"""
        if pil_img:
            self._last_image = pil_img.copy()
            LOGGER.debug(
                "%s: Output Image: %s.",
                self._file_name,
                image_id if image_id else self._shared.vac_json_id,
            )
            if self._shared.show_vacuum_state:
                pil_img = await self.processor.run_async_draw_image_text(
                    pil_img, self._shared.user_colors[8]
                )
        else:
            if self._last_image is not None:
                LOGGER.debug("%s: Output Last Image.", self._file_name)
                pil_img = self._last_image
            else:
                LOGGER.debug("%s: Output Gray Image.", self._file_name)
                # Use synchronous fallback since we're in a thread pool context
                # and only need a gray image, not file loading
                pil_img = Image.new("RGB", (800, 600), "gray")
        self._image_w = pil_img.width
        self._image_h = pil_img.height
        buffered = BytesIO()
        try:
            pil_img.save(buffered, format="PNG")
            return buffered.getvalue()
        finally:
            buffered.close()

    def process_pil_to_bytes(self, pil_img, image_id: str = None):
        """Process the PIL image to bytes.

        This is a synchronous wrapper around the async conversion function,
        designed to be called from a thread pool.
        """
        # Use asyncio.run which properly manages the event loop lifecycle
        try:
            return asyncio.run(self.async_pil_to_bytes(pil_img, image_id))
        except Exception as e:
            LOGGER.error("Error in process_pil_to_bytes: %s", str(e), exc_info=True)
            return None

    async def run_async_pil_to_bytes(self, pil_img, image_id: str = None):
        """Thread function to process the image data using persistent thread pool."""
        try:
            result = await self.thread_pool.run_in_executor(
                "camera",
                self.process_pil_to_bytes,
                pil_img,
                image_id,
            )
            return result
        except Exception as e:
            LOGGER.error("Error converting image to bytes: %s", str(e), exc_info=True)
            return None

    async def handle_vacuum_start(self, event):
        """Handle the event_vacuum_start event."""
        LOGGER.debug("Received event: %s, Data: %s", event.event_type, str(event.data))
        self._shared.reset_trims()  # requires valetudo_map_parser >0.1.9b41
        LOGGER.debug("%s Trims cleared: %s", self._file_name, self._shared.trims)

    async def _debounced_obstacle_handler(self, event):
        """Handler that debounces incoming obstacle view events."""
        # Store the latest event data
        self._latest_obstacle_event = event
        # Trigger the debouncer - it will call _process_obstacle_event after cooldown
        await self._obstacle_view_debouncer.async_call()

    async def _process_obstacle_event(self):
        """Process the latest obstacle event after debouncing."""
        if not hasattr(self, '_latest_obstacle_event'):
            LOGGER.debug("%s: No obstacle event data available for processing", self._file_name)
            return

        event = self._latest_obstacle_event
        LOGGER.debug(
            "%s: Processing debounced obstacle event: %s",
            self._file_name,
            str(event.data)
        )
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
                LOGGER.debug("%s: Restoring the backup image.", self._file_name)
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
        if self._shared.camera_mode in [CameraModes.OBSTACLE_DOWNLOAD, CameraModes.OBSTACLE_SEARCH]:
            LOGGER.debug(
                "%s: Already processing obstacle view (mode: %s), ignoring request",
                self._file_name,
                self._shared.camera_mode,
            )
            return self.Image

        if (
            obstacles_data
            and self._shared.camera_mode == CameraModes.MAP_VIEW
        ):
            if event.data.get("entity_id") != self.entity_id:
                return await _set_camera_mode(CameraModes.MAP_VIEW, "Entity ID mismatch")
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
                            fut=self.processor.download_image(nearest_obstacle["link"], DOWNLOAD_TIMEOUT),
                            timeout=(DOWNLOAD_TIMEOUT + 1), # dead man switch, do not remove.
                        )
                    except asyncio.TimeoutError:
                        LOGGER.warning("%s: Image download timed out.", self._file_name)
                        return await _set_map_view_mode(
                            "Obstacle image download timed out."
                        )

                    # Process the image if download was successful
                    if image_data is not None:
                        await _set_camera_mode(CameraModes.OBSTACLE_VIEW, "Image downloaded successfully")
                        try:
                            start_time = time.perf_counter()
                            # Open the downloaded image with PIL
                            pil_img = await self.hass.async_create_task(
                                self.processor.async_open_image(image_data)
                            )
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
                                resize_result = await async_resize_image(params=resize_data)
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

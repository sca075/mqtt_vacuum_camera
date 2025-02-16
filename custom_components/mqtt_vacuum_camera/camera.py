"""
Camera
Version: v2025.2.2
"""

from __future__ import annotations

import asyncio
from asyncio import gather, get_event_loop
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
import logging
import math
import os
import platform
import time
from typing import Any, Optional

from PIL import Image
from homeassistant import config_entries, core
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.const import CONF_UNIQUE_ID, MATCH_ALL
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo as Dev_Info
from homeassistant.helpers.entity import DeviceInfo as Entity_Info
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from psutil_home_assistant import PsutilWrapper as ProcInsp
from valetudo_map_parser.config.types import SnapshotStore, TrimsData
from valetudo_map_parser.config.utils import ResizeParams, async_resize_image

from .common import RedactIPFilter, get_vacuum_unique_id_from_mqtt_topic
from .const import (
    ATTR_FRIENDLY_NAME,
    ATTR_JSON_DATA,
    ATTR_SNAPSHOT_PATH,
    ATTR_VACUUM_TOPIC,
    CAMERA_STORAGE,
    CONF_VACUUM_IDENTIFIERS,
    DOMAIN,
    NOT_STREAMING_STATES,
    CameraModes,
)
from .snapshots.snapshot import Snapshots
from .utils.camera.camera_processing import CameraProcessor
from .utils.colors_man import ColorsManagment
from .utils.files_operations import (
    async_get_active_user_language,
    async_load_file,
    is_auth_updated,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SCAN_INTERVAL = timedelta(seconds=3)
_LOGGER = logging.getLogger(__name__)
_LOGGER.addFilter(RedactIPFilter())


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
        self._vac_json_available = None
        self._cpu_percent = None
        self._init_clear_www_folder()
        self._last_image = None
        self._update_time = None
        self._rrm_data = False  # Check for rrm data
        # get the colours used in the maps.
        self._colours = ColorsManagment(self._shared)
        self._colours.set_initial_colours(device_info)
        # Create the processor for the camera.
        self.processor = CameraProcessor(self.hass, self._shared)
        # Listen to the vacuum.start event
        self.uns_event_vacuum_start = self.hass.bus.async_listen(
            "event_vacuum_start", self.handle_vacuum_start
        )
        self.uns_event_obstacle_coordinates = self.hass.bus.async_listen(
            "mqtt_vacuum_camera_obstacle_coordinates", self.handle_obstacle_view
        )

    @staticmethod
    def _start_up_logs():
        """Logs the machine running the component data"""
        _LOGGER.info("System Release: %r, %r", platform.node(), platform.release())
        _LOGGER.info("System Version: %r", platform.version())
        _LOGGER.info("System Machine: %r", platform.machine())
        _LOGGER.info("Python Version: %r", platform.python_version())
        _LOGGER.info(
            "Memory Available: %r and In Use: %r",
            round((ProcInsp().psutil.virtual_memory().available / (1024 * 1024)), 1),
            round((ProcInsp().psutil.virtual_memory().used / (1024 * 1024)), 1),
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
        if self._mqtt:
            await self._mqtt.async_unsubscribe_from_topics()

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
        # Update with the shared attributes generated by SharedData
        attributes.update(self._shared.generate_attributes())

        return attributes

    @property
    def should_poll(self) -> bool:
        """ON/OFF Camera Polling Based on Camera Mode."""
        POLLING_STATES = {
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

        self._should_poll = POLLING_STATES.get(self._shared.camera_mode, False)
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

    def empty_if_no_data(self) -> Image:
        """
        It will return the last image if available or
        an empty image if there are no data.
        """
        if self._last_image:
            _LOGGER.debug("%s: Returning Last image.", self._file_name)
            return self._last_image
        # Check if the snapshot file exists
        _LOGGER.info("%s: Searching for %s.", self._file_name, self.snapshot_img)
        if os.path.isfile(self.snapshot_img):
            # Load the snapshot image
            self._last_image = Image.open(self.snapshot_img)
            _LOGGER.debug("%s: Returning Snapshot image.", self._file_name)
            return self._last_image
        # Create an empty image with a gray background
        empty_img = Image.new("RGB", (800, 600), "gray")
        _LOGGER.info("%s: Returning Empty image.", self._file_name)
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
            if self.Image is not None:
                return self.camera_image(self._image_w, self._image_h)

        # Map View Processing
        if is_auth_updated(self):
            # Get the active user language
            self._shared.user_language = await async_get_active_user_language(self.hass)
        if not self._mqtt:
            _LOGGER.debug("%s: No MQTT data available.", self._file_name)
            # return last/empty image if no MQTT or CPU usage too high.
            await self._handle_no_mqtt_data()

        # If we have data from MQTT, we process the image.
        await self._update_vacuum_state()

        pid = os.getpid()  # Start to log the CPU usage of this PID.
        proc = ProcInsp().psutil.Process(pid)  # Get the process PID.
        process_data = await self._mqtt.is_data_available()
        if process_data and self._shared.camera_mode == CameraModes.MAP_VIEW:
            # to calculate the cycle time for frame adjustment.
            start_time = time.perf_counter()
            self._log_cpu_usage(proc)
            self._processing = True
            # if the vacuum is working, or it is the first image.
            if self.is_streaming:
                # grab the image from MQTT.
                self._shared.image_grab = True
                self._shared.snapshot_take = False
                self._shared.frame_number = self.processor.get_frame_number()
                _LOGGER.info(
                    "%s: Camera image data update available: %r",
                    self._file_name,
                    process_data,
                )
            try:
                parsed_json, is_a_test = await self._process_parsed_json()
            except ValueError:
                self._vac_json_available = "Error"
                pass
            else:
                # Just in case, let's check that the data is available.
                if parsed_json is not None:
                    if self._rrm_data:
                        self._shared.destinations = await self._mqtt.get_destinations()
                        pil_img = await self.hass.async_create_task(
                            self.processor.run_async_process_valetudo_data(
                                self._rrm_data
                            )
                        )
                    elif self._rrm_data is None:
                        _LOGGER.debug("Image creation in progress")
                        pil_img = await self.hass.async_create_task(
                            self.processor.run_async_process_valetudo_data(parsed_json)
                        )
                    else:
                        # if no image was processed empty or last snapshot/frame
                        if not is_a_test:
                            pil_img = self.empty_if_no_data()
                        else:
                            _LOGGER.debug("Producing test mode image")
                            pil_img = await self.hass.async_create_task(
                                self.processor.run_async_process_valetudo_data(
                                    parsed_json
                                )
                            )

                    # update the image
                    self._last_image = pil_img
                    self.Image = await self.hass.async_create_task(
                        self.run_async_pil_to_bytes(pil_img)
                    )
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
                    # take a snapshot if we meet the conditions.
                    await self._take_snapshot(parsed_json, pil_img)

                    _LOGGER.debug("%s: Image update complete", self._file_name)
                    self._update_frame_interval(start_time)
                else:
                    _LOGGER.info(
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
        pil_img = self.empty_if_no_data()
        self.Image = await self.hass.async_create_task(
            self.run_async_pil_to_bytes(pil_img)
        )
        return self.camera_image(pil_img.width, pil_img.height)

    async def _process_parsed_json(self, test_mode: bool = False):
        """Process the parsed JSON data and return the generated image."""
        if test_mode:
            _LOGGER.debug("Camera Test Mode Active...")
            parsed_json = await async_load_file(
                file_to_load="custom_components/mqtt_vacuum_camera/snapshots/test.json",
                is_json=True,
            )
            self._shared.camera_mode = CameraModes.MAP_VIEW
            return parsed_json, test_mode
        parsed_json = await self._mqtt.update_data(self._shared.image_grab)
        if not parsed_json:
            self._vac_json_available = "Error"
            self.Image = await self.hass.async_create_task(
                self.run_async_pil_to_bytes(self.empty_if_no_data())
            )
            self.camera_image(self._image_w, self._image_h)
            _LOGGER.warning(
                "%s: No JSON data available. Camera Suspended.", self._file_name
            )
            self._should_pull = False

        if parsed_json[1] == "Rand256":
            self._shared.is_rand = True
            self._rrm_data = parsed_json[0]
        else:
            parsed_json = parsed_json[0]
            self._rrm_data = None

        self._vac_json_available = "Success"
        return parsed_json, test_mode

    async def _take_snapshot(self, parsed_json, pil_img):
        """Take a snapshot if conditions are met."""
        if self._shared.snapshot_take and pil_img:
            if self._shared.is_rand:
                await self.take_snapshot(self._rrm_data, pil_img)
            else:
                await self.take_snapshot(parsed_json, pil_img)

    def _log_cpu_usage(self, proc):
        """Log the CPU usage."""
        self._cpu_percent = round(
            ((proc.cpu_percent() / int(ProcInsp().psutil.cpu_count())) / 10), 1
        )

    def _log_memory_usage(self, proc):
        """Log the memory usage."""
        memory_percent = round(
            (
                (proc.memory_info()[0] / 2.0**30)
                / (ProcInsp().psutil.virtual_memory().total / 2.0**30)
            )
            * 100,
            2,
        )
        _LOGGER.debug(
            "%s: Camera Memory: GB in use %.2f / system available %.2f%%.",
            self._file_name,
            round(proc.memory_info()[0] / 2.0**30, 2),
            memory_percent,
        )

    def _update_frame_interval(self, start_time):
        """Update the frame interval based on processing time."""
        processing_time = round((time.perf_counter() - start_time), 3)
        self._attr_frame_interval = max(0.1, processing_time)

    async def async_pil_to_bytes(
        self, pil_img, image_id: str = None
    ) -> Optional[bytes]:
        """Convert PIL image to bytes"""
        if pil_img:
            self._last_image = pil_img
            _LOGGER.debug(
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
                _LOGGER.debug("%s: Output Last Image.", self._file_name)
                pil_img = self._last_image
            else:
                _LOGGER.debug("%s: Output Gray Image.", self._file_name)
                pil_img = self.empty_if_no_data()
        self._image_w = pil_img.width
        self._image_h = pil_img.height
        buffered = BytesIO()
        pil_img.save(buffered, format="PNG")
        bytes_data = buffered.getvalue()
        del buffered, pil_img
        return bytes_data

    def process_pil_to_bytes(self, pil_img, image_id: str = None):
        """Async function to process the image data from the Vacuum Json data."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self.async_pil_to_bytes(pil_img, image_id))
        finally:
            loop.close()
        return result

    async def run_async_pil_to_bytes(self, pil_img, image_id: str = None):
        """Thread function to process the image data from the Vacuum Json data."""
        num_processes = 1
        pil_img_list = [pil_img for _ in range(num_processes)]
        loop = get_event_loop()

        with ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=f"{self._file_name}_camera"
        ) as executor:
            tasks = [
                loop.run_in_executor(
                    executor, self.process_pil_to_bytes, pil_img, image_id
                )
                for pil_img in pil_img_list
            ]
            images = await gather(*tasks)

        if isinstance(images, list) and len(images) > 0:
            result = images[0]
        else:
            result = None

        return result

    async def handle_vacuum_start(self, event):
        """Handle the event_vacuum_start event."""
        _LOGGER.debug("Received event: %s, Data: %s", event.event_type, str(event.data))
        self._shared.trims = TrimsData.clear
        _LOGGER.debug("%s Trims cleared: %s", self._file_name, self._shared.trims)

    async def handle_obstacle_view(self, event):
        """Handle the event mqtt_vacuum_camera_obstacle_coordinates."""

        async def _set_map_view_mode(reason: str = None):
            """Set the camera mode to MAP_VIEW."""
            self._shared.camera_mode = CameraModes.MAP_VIEW
            _LOGGER.debug(
                "%s: Camera Mode Change to %s",
                self._file_name,
                self._shared.camera_mode,
                reason if reason else ", ''.",
            )
            if self._image_bk:
                _LOGGER.debug("%s: Restoring the backup image.", self._file_name)
                self.Image = self._image_bk
                return self.camera_image(self._image_w, self._image_h)
            return

        async def _set_camera_mode(mode_of_camera: CameraModes, reason: str = None):
            """Set the camera mode."""
            self._shared.camera_mode = mode_of_camera
            if mode_of_camera == CameraModes.OBSTACLE_SEARCH and not self._image_bk:
                self._image_bk = self.Image

            _LOGGER.debug(
                "%s: Camera Mode Change to %s",
                self._file_name,
                self._shared.camera_mode,
                reason if reason else ", ''.",
            )

        async def _async_find_nearest_obstacle(x, y, all_obstacles):
            """Find the nearest obstacle to the given coordinates."""
            nearest_obstacles = None
            width = self._shared.image_ref_width
            height = self._shared.image_ref_height
            min_distance = round(
                60 * (width / height)
            )  # (60 * aspect ratio) pixels distance
            _LOGGER.debug(
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

        _LOGGER.debug(
            "%s: Received event: %s, Data: %s",
            self._file_name,
            str(event.event_type),
            str(event.data),
        )
        # Check if we are in obstacle view and switch back to map view
        if self._shared.camera_mode == CameraModes.OBSTACLE_VIEW:
            return await _set_map_view_mode("Obstacle View Exit Requested.")

        if (
            self._shared.obstacles_data
            and self._shared.camera_mode == CameraModes.MAP_VIEW
        ):
            if event.data.get("entity_id") == self.entity_id:
                await _set_camera_mode(CameraModes.OBSTACLE_SEARCH)
                coordinates = event.data.get("coordinates")
                if coordinates:
                    obstacles = self._shared.obstacles_data
                    coordinates_x = coordinates.get("x")
                    coordinates_y = coordinates.get("y")
                    # Find the nearest obstacle
                    nearest_obstacle = await _async_find_nearest_obstacle(
                        coordinates_x, coordinates_y, obstacles
                    )

                    if nearest_obstacle:
                        _LOGGER.debug(
                            "%s: Nearest obstacle found: %r",
                            self._file_name,
                            nearest_obstacle,
                        )
                        if nearest_obstacle["link"]:
                            await _set_camera_mode(
                                mode_of_camera=CameraModes.OBSTACLE_DOWNLOAD,
                                reason=f"Downloading image: {nearest_obstacle['link']}",
                            )
                            try:
                                temp_image = await asyncio.wait_for(
                                    fut=self.processor.download_image(
                                        nearest_obstacle["link"]
                                    ),
                                    timeout=10,
                                )
                            except asyncio.TimeoutError:
                                return await _set_map_view_mode(
                                    "Image download timeout."
                                )
                            except Exception as e:
                                return await _set_map_view_mode(
                                    f"Error downloading image: {e}"
                                )
                        else:
                            return await _set_map_view_mode(
                                "No link found for the obstacle image."
                            )
                        if temp_image is not None:
                            await _set_camera_mode(CameraModes.OBSTACLE_VIEW)
                            try:
                                start_time = time.perf_counter()
                                # Open the downloaded image with PIL
                                pil_img = await self.hass.async_create_task(
                                    self.processor.async_open_image(temp_image)
                                )
                                # Resize the image if resize_to is provided
                                width = self._shared.image_ref_width
                                height = self._shared.image_ref_height
                                resize_data = ResizeParams(
                                    pil_img=pil_img,
                                    width=width,
                                    height=height,
                                    aspect_ratio=self._shared.image_aspect_ratio,
                                    crop_size=[],
                                    is_rand=False,
                                    offset_func=None,
                                )
                                resized_image, _ = await async_resize_image(
                                    params=resize_data
                                )
                                self.Image = await self.hass.async_create_task(
                                    self.run_async_pil_to_bytes(
                                        resized_image,
                                        image_id=nearest_obstacle["label"],
                                    )
                                )
                                end_time = time.perf_counter()
                                _LOGGER.debug(
                                    "%s: Image processing time: %r seconds",
                                    self._file_name,
                                    end_time - start_time,
                                )
                                return
                            except Exception as e:
                                _LOGGER.warning(
                                    "%s: Unexpected Error processing image: %r",
                                    self._file_name,
                                    e,
                                    exc_info=True,
                                )
                                return await _set_map_view_mode()
                        else:
                            return await _set_map_view_mode("No image downloaded.")
                    else:
                        return await _set_map_view_mode("No nearby obstacle found.")
        else:
            return await _set_map_view_mode("No obstacles data available.")

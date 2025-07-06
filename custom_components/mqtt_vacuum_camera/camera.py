"""
MQTT Vacuum Camera Entity - Simple Implementation
Camera just handles PIL to bytes conversion, coordinator does all processing.
Version: 2025.6.0
"""

from __future__ import annotations

from datetime import timedelta
import os
from io import BytesIO
import time
from typing import Any, Optional
from PIL import Image

from homeassistant.core import callback
from homeassistant import config_entries, core
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.const import CONF_UNIQUE_ID, MATCH_ALL
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo as Dev_Info
from homeassistant.helpers.entity import DeviceInfo as Entity_Info
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from valetudo_map_parser.config.types import SnapshotStore
from valetudo_map_parser.config.colors import ColorsManagement

from .coordinator import CameraCoordinator
from .common import get_vacuum_unique_id_from_mqtt_topic
from .const import (
    ATTR_FRIENDLY_NAME,
    ATTR_JSON_DATA,
    ATTR_SNAPSHOT_PATH,
    ATTR_VACUUM_TOPIC,
    CAMERA_STORAGE,
    CONF_VACUUM_IDENTIFIERS,
    DOMAIN,
    LOGGER,
    CameraModes,
    NOT_STREAMING_STATES,
)
from .snapshots.snapshot import Snapshots
from .utils.camera.obstacle_handler import ObstacleViewHandler

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
) -> None:
    """Setup camera from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    coordinators = hass.data[DOMAIN][config_entry.entry_id]["coordinators"]
    camera_coordinator = coordinators["camera"]
    # Update our config to and eventually add or remove option.
    if config_entry.options:
        config.update(config_entry.options)

    # Create camera entity
    camera = [MQTTVacuumCamera(camera_coordinator, config)]

    # Add entities
    async_add_entities(camera, update_before_add=False)


class MQTTVacuumCamera(CoordinatorEntity[CameraCoordinator], Camera):
    """
    Simple MQTT Vacuum Camera Entity.

    Coordinator handles all processing (MQTT → JSON → PIL).
    Camera just handles PIL → bytes conversion and display.
    """

    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset({MATCH_ALL})
    _attr_should_poll = False  # CoordinatorEntity handles updates automatically

    def __init__(
        self, coordinator: CameraCoordinator, device_info: dict[str, Any]
    ) -> None:
        """Initialize the simple camera entity."""
        super().__init__(coordinator)
        Camera.__init__(self)

        self.hass = coordinator.hass
        self.coordinator = coordinator
        self._device_info = device_info

        # Basic attributes
        self._attr_model = "MQTT Vacuums"
        self._attr_brand = "MQTT Vacuum Camera"
        self._attr_name = "Camera"
        self._attr_is_on = True
        self._attr_motion_detection_enabled = False
        self._attr_frame_interval = 1.0
        self._attr_should_poll = True

        # Core data from coordinator
        self._file_name = coordinator.file_name
        self._shared = coordinator.shared
        self._mqtt_listen_topic = coordinator.vacuum_topic

        # Camera Functions
        self._homeassistant_path = self.hass.config.path()  # get Home Assistant path
        self._storage_path, self.snapshot_img, self.log_file = self._init_paths()
        self.thread_pool = self.coordinator.thread_pool.get_instance(self._file_name)
        self._colours = ColorsManagement(self._shared)
        self._snapshots = Snapshots(self.hass, self._shared)
        self._obstacle_handler = None
        self._init_clear_www_folder()

        # Unique ID and identifiers
        self._attr_unique_id = device_info.get(
            CONF_UNIQUE_ID,
            get_vacuum_unique_id_from_mqtt_topic(self._mqtt_listen_topic),
        )
        self._identifiers = device_info.get(CONF_VACUUM_IDENTIFIERS)

        # Image state
        self.Image: Optional[bytes] = None
        self.image_bk: Optional[bytes] = None
        self._obstacle_image: Optional[bytes] = None
        self._last_image: Optional[Image.Image] = None
        self._image_w: Optional[int] = None
        self._image_h: Optional[int] = None

        # Processing state
        self._processing = True
        self._image_receive_time: Optional[float] = None
        self._vac_json_available = "Initializing"

        # Performance tracking
        self._timing_log_counter = 0
        self.uns_event_obstacle_coordinates = self.hass.bus.async_listen(
            "mqtt_vacuum_camera_obstacle_coordinates", self._debounced_obstacle_handler
        )
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

    def _init_paths(self):
        """Initialize Camera Paths"""
        storage_path = f"{self.hass.config.path(STORAGE_DIR)}/{CAMERA_STORAGE}"
        if not os.path.exists(storage_path):
            storage_path = f"{self._homeassistant_path}/{STORAGE_DIR}"
        snapshot_img = f"{storage_path}/{self._file_name}.png"
        log_file = f"{storage_path}/{self._file_name}.zip"
        return storage_path, snapshot_img, log_file

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

    def _init_obstacle_handler(self):
        """Initialize the obstacle handler with required dependencies."""
        if not self._obstacle_handler:
            self._obstacle_handler = ObstacleViewHandler(
                self._shared,
                self._file_name,
                self.coordinator.processor,
                self.hass,
                self.entity_id,
                self.thread_pool,
            )

    async def async_added_to_hass(self) -> None:
        """Handle entity added to Home Assistant."""
        await super().async_added_to_hass()

        # Initialize colors
        self._colours.set_initial_colours(self._device_info)

        # Set default language
        self._shared.user_language = "en"

        # Subscribe to MQTT topics
        await self.coordinator.async_subscribe_mqtt()

        # Set camera mode and initial state
        self._shared.camera_mode = CameraModes.MAP_VIEW
        self._shared.image_grab = True

        LOGGER.debug("Simple camera entity added to HA for: %s", self._file_name)

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal from Home Assistant."""
        await super().async_will_remove_from_hass()

        # Unsubscribe from MQTT topics
        await self.coordinator.async_unsubscribe_mqtt()

        LOGGER.debug("Simple camera entity removed from HA for: %s", self._file_name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        if self._shared.camera_mode == CameraModes.OBSTACLE_VIEW:
            if self._obstacle_image is not None:
                self.Image = self._obstacle_image
                self.async_write_ha_state()
                return

        # Process new image data
        if self.coordinator.data and self.coordinator.data.get("pil_image"):
            LOGGER.debug(
                "Processing PIL image from coordinator for: %s", self._file_name
            )
            if self.is_streaming:
                self._shared.image_grab = True
                self._shared.snapshot_take = False
                self._shared.frame_number = self.coordinator.processor.get_frame_number()
            self._processing = True
            try:
                # Get PIL image from coordinator
                pil_img = self.coordinator.data["pil_image"]
                # Convert PIL to bytes for camera display
                self.hass.async_create_task(self._async_convert_and_update(pil_img))

            except Exception as err:
                LOGGER.error(
                    "Error processing coordinator update for %s: %s",
                    self._file_name,
                    err,
                )
                self._vac_json_available = "Error"
                self._processing = False
        else:
            # Image backup
            if (
                self._shared.vacuum_state == "docked"
                and self._shared.camera_mode == CameraModes.MAP_VIEW
            ):
                self.image_bk = self.Image
            elif (
                self._shared.camera_mode == CameraModes.MAP_VIEW
                and self._shared.vacuum_state != "docked"
            ):
                self.image_bk = None
            LOGGER.debug(
                "No PIL image available from coordinator for: %s", self._file_name
            )

    async def _async_convert_and_update(self, pil_img):
        """Convert PIL to bytes and update state."""
        try:
            # Convert PIL to bytes for camera display
            if self._processing or self.Image is None:
                self.Image = await self.async_pil_to_bytes(pil_img)
                self._processing = False

            # Store last image
            self._last_image = pil_img.copy()
            self._vac_json_available = "Success"

            LOGGER.debug("Image conversion complete for: %s", self._file_name)

        except Exception as err:
            LOGGER.error(
                "Error converting PIL to bytes for %s: %s", self._file_name, err
            )
            self._vac_json_available = "Error"
        finally:
            # Update HA state
            self.async_write_ha_state()

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
                pil_img = await self.coordinator.processor.async_draw_image_text(
                    pil_img,
                    self._shared.user_colors[8],
                    self._shared.vacuum_status_font,
                    self._shared.vacuum_status_position,
                )
        else:
            if self._last_image is not None:
                LOGGER.debug("%s: Output Last Image.", self._file_name)
                pil_img = self._last_image
            else:
                LOGGER.debug("%s: Output Gray Image.", self._file_name)
                pil_img = Image.new("RGB", (800, 600), "gray")
        self._image_w = pil_img.width
        self._image_h = pil_img.height
        buffered = BytesIO()
        try:
            pil_img.save(buffered, format="PNG")
            return buffered.getvalue()
        except Exception as err:
            LOGGER.error(
                "Error converting PIL to bytes for %s: %s", self._file_name, err
            )
            return None
        finally:
            buffered.close()

    async def run_async_pil_to_bytes(self, pil_img, image_id: str = None):
        """Thread function to process the image data using persistent thread pool."""
        try:
            result = await self.thread_pool.run_async_in_executor(
                "camera",
                self.async_pil_to_bytes,
                pil_img,
                image_id,
            )
            return result
        except Exception as e:
            LOGGER.error("Error converting image to bytes: %s", str(e), exc_info=True)
            return None

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

        self._attr_should_poll = poling_states.get(self._shared.camera_mode, False)
        return self._attr_should_poll

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
            ATTR_SNAPSHOT_PATH: f"/www/snapshot_{self._file_name}.png",
        }
        if self._shared:
            attributes.update(self._shared.generate_attributes())
        return attributes

    @property
    def device_info(self):
        """Return the device info."""
        device_info = Dev_Info if Dev_Info else Entity_Info
        return device_info(identifiers=self._identifiers)

    def camera_image(
        self, width: Optional[int] = None, height: Optional[int] = None
    ) -> Optional[bytes]:
        """Camera Image"""
        return self.Image

    def turn_on(self) -> None:
        """Camera Turn On"""
        if self._shared:
            self._shared.camera_mode = CameraModes.CAMERA_ON

    def turn_off(self) -> None:
        """Camera Turn Off"""
        if self._shared:
            self._shared.camera_mode = CameraModes.CAMERA_OFF

    async def take_snapshot(self, json_data: Any, image_data: Image.Image) -> None:
        """Camera Automatic Snapshots."""
        partial_snapshot = SnapshotStore()
        await partial_snapshot.async_set_snapshot_save_data(self._file_name)
        await self._snapshots.run_async_take_snapshot(json_data, image_data)

    @staticmethod
    def _load_snapshot_image(snapshot_path: str) -> Image.Image:
        """
        Synchronous helper function to load snapshot image from file.
        This function is designed to be called from a thread pool.
        """
        with Image.open(snapshot_path) as img:
            return img.copy()

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

    async def handle_vacuum_start(self, event):
        """Handle the event_vacuum_start event."""
        LOGGER.debug("Received event: %s, Data: %s", event.event_type, str(event.data))
        self._shared.reset_trims()  # requires valetudo_map_parser >0.1.9b41
        LOGGER.debug("%s Trims cleared: %s", self._file_name, self._shared.trims)

    async def _debounced_obstacle_handler(self, event):
        """Handler that debounce incoming obstacle view events."""
        # Store the latest event data
        self._latest_obstacle_event = event
        # Trigger the debouncer - it will call _process_obstacle_event after cooldown
        await self._obstacle_view_debouncer.async_call()

    async def _process_obstacle_event(self):
        """Process the latest obstacle event after debouncing."""
        if not hasattr(self, "_latest_obstacle_event"):
            LOGGER.debug(
                "%s: No obstacle event data available for processing", self._file_name
            )
            return

        event = self._latest_obstacle_event
        LOGGER.debug(
            "%s: Processing debounced obstacle event: %s",
            self._file_name,
            str(event.data),
        )
        await self.handle_obstacle_view(event)

    async def handle_obstacle_view(self, event):
        """Handle the event mqtt_vacuum_camera_obstacle_coordinates."""
        if not self._obstacle_handler:
            self._init_obstacle_handler()
        return await self._obstacle_handler.handle_obstacle_view(dict(event.data), self)

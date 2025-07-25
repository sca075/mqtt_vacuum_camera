"""
MQTT Vacuum Camera Entity
Camera just handles PIL to bytes conversion, coordinator does all processing.
Version: 2025.7.1
"""

from __future__ import annotations

import os
from typing import Any, Optional
from PIL import Image

from homeassistant.core import callback
from homeassistant.components.camera import CameraEntityFeature
from homeassistant.const import CONF_UNIQUE_ID, MATCH_ALL
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
    LOGGER,
    CameraModes,
)
from .snapshots.snapshot import Snapshots
from .utils.thread_pool import TaskQueue
from .utils.camera.obstacle_handler import ObstacleViewHandler


class MQTTVacuumCoordinatorEntity(CoordinatorEntity[CameraCoordinator]):
    """
    MQTT Vacuum Camera Entity.

    Coordinator handles all processing (MQTT → JSON → PIL).
    Camera just handles PIL → bytes conversion and display.
    """

    def __init__(
        self, coordinator: CameraCoordinator, device_info: dict[str, Any]
    ) -> None:
        """Initialize the simple camera entity."""
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._unrecorded_attributes = frozenset({MATCH_ALL})
        self._attr_should_poll = (
            False  # CoordinatorEntity handles updates automatically
        )
        self.hass = coordinator.hass
        self.coordinator = coordinator
        self._device_info = device_info
        self.task_async = TaskQueue()
        # Basic attributes
        self._attr_model = "MQTT Vacuums"
        self._attr_brand = "MQTT Vacuum Camera"
        self._attr_name = f"Camera {coordinator.file_name}"
        self._attr_is_on = True
        self._attr_motion_detection_enabled = False
        self._attr_frame_interval = 1.0
        self._attr_is_streaming = True
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

        LOGGER.debug("Camera entity added to HA for: %s", self._file_name)

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal from Home Assistant."""
        await super().async_will_remove_from_hass()

        # Unsubscribe from MQTT topics
        await self.coordinator.async_unsubscribe_mqtt()
        self._obstacle_view_debouncer.async_shutdown()
        self.uns_event_obstacle_coordinates.async_remove()
        self.uns_event_vacuum_start.async_remove()
        self.coordinator.processor._unsub_dispatcher = None
        self.coordinator.processor._unsub_dispatcher_ready = None
        self.coordinator._unsub_dispatcher_ready = None

        LOGGER.debug("Camera entity removed from HA for: %s", self._file_name)

    @callback
    def _handle_coordinator_update(self) -> bytes:
        """Handle updated data from the coordinator."""

        if self._shared.camera_mode == CameraModes.OBSTACLE_VIEW:
            if self._obstacle_image is not None:
                self.Image = self._obstacle_image
                self.async_write_ha_state()
            return self.Image
        # Get PIL image from coordinator
        pil_img = self.coordinator.get_map_image()

        # Check if automatic snapshot should be taken
        if (
            self._shared.snapshot_take
            and self._shared.enable_snapshots
            and self._shared.camera_mode == CameraModes.MAP_VIEW
        ):
            # Use current PIL image or last available image for snapshot
            snapshot_image = pil_img if pil_img else self._last_image
            if snapshot_image:
                LOGGER.debug(
                    "Taking automatic snapshot for %s (snapshot_take flag set)",
                    self._file_name,
                )
                self.hass.async_create_task(
                     self.take_snapshot({}, snapshot_image), "take_snapshot"
                )
                # Reset the flag after taking snapshot
                self._shared.snapshot_take = False

        # Process new image data
        if pil_img:
            LOGGER.debug("Updating image from coordinator for: %s", self._file_name)
            try:
                self._attr_frame_interval = (
                    self.coordinator.processor.get_processing_time()
                )
                self.Image = self.coordinator.processor.get_image_bytes()
                self._image_w = pil_img.width
                self._image_h = pil_img.height
                self._vac_json_available = "Success"
                self.coordinator.processor._processing_lock = False

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
        self.async_write_ha_state()
        return self.camera_image(self._image_w, self._image_h)

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
    def is_streaming(self) -> bool:
        """Return true if the device is streaming."""
        self._attr_is_streaming = self.coordinator.should_stream
        return self._attr_is_streaming

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return CameraEntityFeature.ON_OFF | CameraEntityFeature.STREAM

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

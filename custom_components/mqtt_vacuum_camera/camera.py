"""
Camera
Last Updated on version: 2025.12.0
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from io import BytesIO
import os
from pathlib import Path
from typing import Optional

from homeassistant import config_entries, core
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.const import CONF_UNIQUE_ID, MATCH_ALL
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo as Dev_Info
from homeassistant.helpers.entity import DeviceInfo as Entity_Info
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from valetudo_map_parser.config.colors import ColorsManagement

from .common import get_vacuum_unique_id_from_mqtt_topic
from .const import (
    ATTR_FRIENDLY_NAME,
    ATTR_VACUUM_TOPIC,
    CAMERA_SCAN_INTERVAL_S,
    CAMERA_STORAGE,
    CONF_VACUUM_IDENTIFIERS,
    DOMAIN,
    FRAME_INTERVAL_S,
    LOGGER,
    RENDER_TIMEOUT_S,
    CameraModes,
)
from .types import (
    CameraContext,
    CameraDeviceInfo,
    CameraImageState,
    CameraMQTTConfig,
    CameraPathsConfig,
    CameraProcessors,
    CameraSettings,
)
from .utils.camera.camera_processing import CameraProcessor
from .utils.camera.obstacle_view import ObstacleView, ObstacleViewContext
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


class MQTTCamera(CoordinatorEntity, Camera):  # pylint: disable=too-many-instance-attributes
    """
    Render the vacuum map and the vacuum state for:
    Valetudo Hypfer and rand256 Firmwares Vacuums maps.
    From PI4 up to all other Home Assistant supported platforms.

    Note: Instance attributes count includes required Home Assistant Camera
    base class attributes (_attr_*). Core logic uses 7 grouped dataclasses:
    context, device, mqtt, paths, image_state, processors, settings.
    """

    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset({MATCH_ALL})

    # noinspection PyUnusedLocal
    def __init__(self, coordinator, device_info):
        super().__init__(coordinator)
        Camera.__init__(self)

        # 1. Core context (grouped)
        self.context = CameraContext(
            hass=coordinator.hass,
            shared=coordinator.shared,
            file_name=coordinator.file_name,
            coordinator=coordinator,
        )

        # 2. Device info (grouped)
        self.device = CameraDeviceInfo(
            unique_id=device_info.get(
                CONF_UNIQUE_ID,
                get_vacuum_unique_id_from_mqtt_topic(coordinator.vacuum_topic),
            ),
            identifiers=device_info.get(CONF_VACUUM_IDENTIFIERS),
        )

        # 3. MQTT config (grouped)
        self.mqtt = CameraMQTTConfig(
            topic=coordinator.vacuum_topic,
            connector=coordinator.connector,
        )

        # 4. Paths (grouped)
        self.paths = self._init_paths_config()

        # 5. Image state (grouped)
        self.image_state = CameraImageState()

        # 6. Processors (grouped)
        self.processors = self._init_processors(device_info)

        # 7. Settings (grouped)
        self.settings = CameraSettings(
            frame_interval=float(timedelta(seconds=6).total_seconds()),
        )

        # Set Home Assistant entity attributes
        self._attr_model = self.device.model
        self._attr_brand = self.device.brand
        self._attr_name = self.device.name
        self._attr_is_on = self.settings.is_on
        self._attr_unique_id = self.device.unique_id
        self._attr_frame_interval = self.settings.frame_interval
        self._should_poll = self.settings.should_poll

        # Initialize shared settings
        self.context.shared.user_language = "en"
        self.context.shared.image_grab = True

        # Clean up www folder
        self._init_clear_www_folder()

        # Listen to the vacuum.start event
        self.settings.event_listener = self.context.hass.bus.async_listen(
            "event_vacuum_start", self.handle_vacuum_start
        )

    def _init_paths_config(self) -> CameraPathsConfig:
        """Initialize camera paths configuration."""
        homeassistant_path = self.context.hass.config.path()
        storage_root = Path(self.context.hass.config.path(STORAGE_DIR))
        storage_path = storage_root / CAMERA_STORAGE
        if not storage_path.exists():
            # Use the default storage path
            storage_path = Path(homeassistant_path) / STORAGE_DIR
        return CameraPathsConfig(
            homeassistant_path=homeassistant_path,
            storage_path=str(storage_path),
        )

    def _init_processors(self, device_info) -> CameraProcessors:
        """Initialize all processing components."""
        # Get the colours used in the maps
        colours = ColorsManagement(self.context.shared)
        colours.set_initial_colours(device_info)

        # Get thread pool and decompression manager
        thread_pool = ThreadPoolManager.get_instance(self.context.file_name)
        decompression = DecompressionManager.get_instance(self.context.file_name)

        # Create the processor for the camera
        processor = CameraProcessor(self.context.hass, self.context.shared, thread_pool)

        # Initialize ObstacleView manager
        obstacle_context = ObstacleViewContext(
            hass=self.context.hass,
            shared=self.context.shared,
            file_name=self.context.file_name,
            download_image_func=processor.download_image,
            open_image_func=processor.async_open_image,
            pil_to_bytes_func=self._run_async_pil_to_bytes,
        )
        obstacle_view = ObstacleView(obstacle_context)

        return CameraProcessors(
            processor=processor,
            decompression=decompression,
            thread_pool=thread_pool,
            colours=colours,
            obstacle_view=obstacle_view,
        )

    def _init_clear_www_folder(self):
        """Remove PNG snapshots stored in HA config WWW if snapshots are disabled."""
        # If enable_snapshots is disabled, remove any existing snapshot file
        snapshot_path = Path(self.paths.homeassistant_path) / "www" / f"snapshot_{self.context.file_name}.png"
        if not self.context.shared.enable_snapshots and snapshot_path.is_file():
            snapshot_path.unlink()

    async def async_cleanup_all(self):
        """Clean up all dispatcher connections."""
        # Clean up coordinator's own dispatchers
        if self.settings.event_listener:
            self.settings.event_listener()
        # Clean up ObstacleView manager
        if hasattr(self, "processors"):
            await self.processors.obstacle_view.async_cleanup()

    async def async_added_to_hass(self) -> None:
        """Handle entity added to Home Assistant."""
        self.settings.should_poll = True
        _start_image = self.context.shared.last_image
        self.image_state.main_image = await self.context.hass.async_add_executor_job(
            self._pil_to_bytes, _start_image, "Start Up"
        )
        self.context.shared.camera_mode = CameraModes.MAP_VIEW
        # Setup ObstacleView manager
        await self.processors.obstacle_view.async_setup(self.entity_id)
        self.async_schedule_update_ha_state(True)

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal from Home Assistant."""
        await super().async_will_remove_from_hass()
        await self.async_cleanup_all()

        # Unsubscribe from MQTT topics
        if self.mqtt.connector:
            await self.mqtt.connector.async_unsubscribe_from_topics()

        # Shutdown thread pool for this camera instance only
        if hasattr(self, "processors") and self.processors.thread_pool:
            await self.processors.thread_pool.shutdown_instance()
            LOGGER.debug("Thread pool for camera %s shut down", self.context.file_name)

        LOGGER.debug("Camera entity removed from HA for: %s", self.context.file_name)

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
        if self.processors.processor.data:
            self._attr_is_streaming = self.processors.processor.data["image"][
                "streaming"
            ]
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
        if (
            self.context.shared.camera_mode == CameraModes.OBSTACLE_VIEW
            or self.context.shared.binary_image is None
        ):
            width, height = self.image_state.width, self.image_state.height
            return self.image_state.main_image
        # Return the binary image data from the processor
        width, height = self.processors.processor.data["image"]["size"]
        self.image_state.width, self.image_state.height = width, height
        return self.processors.processor.data["image"]["binary"]

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return CameraEntityFeature.ON_OFF

    @property
    def extra_state_attributes(self) -> dict:
        """Return Camera Attributes"""
        attr_data = self.context.shared.to_dict()["attributes"]
        attributes = {
            ATTR_FRIENDLY_NAME: self._attr_name,
            ATTR_VACUUM_TOPIC: self.mqtt.topic,
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

        if isinstance(self.context.shared.camera_mode, bool):
            self.context.shared.camera_mode = (
                CameraModes.MAP_VIEW
                if self.context.shared.camera_mode
                else CameraModes.CAMERA_STANDBY
            )

        self.settings.should_poll = poling_states.get(
            self.context.shared.camera_mode, False
        )
        return self.settings.should_poll

    @property
    def device_info(self):
        """Return the device info."""
        # Use Dev_Info (device_registry) if available, otherwise Entity_Info
        device_info_class = Dev_Info or Entity_Info
        return device_info_class(identifiers=self.device.identifiers)

    def turn_on(self) -> None:
        """Camera Turn On"""
        self.context.shared.camera_mode = CameraModes.CAMERA_ON

    def turn_off(self) -> None:
        """Camera Turn Off"""
        self.context.shared.camera_mode = CameraModes.CAMERA_OFF

    async def _update_vacuum_state(self) -> str:
        """Update a few shared fields; light-weight."""
        self.context.shared.vacuum_battery = (
            await self.mqtt.connector.get_battery_level()
        )
        self.context.shared.vacuum_connection = (
            await self.mqtt.connector.get_vacuum_connection_state()
        )

        if not self.context.shared.vacuum_connection:
            self.context.shared.vacuum_state = "disconnected"
        else:
            self.context.shared.vacuum_state = (
                await self.mqtt.connector.get_vacuum_status()
            )
        return self.context.shared.vacuum_state

    async def async_update(self):
        """Camera Frame Update."""

        # Obstacle View Processing
        if self.context.shared.camera_mode == CameraModes.OBSTACLE_VIEW:
            obstacle_image = self.processors.obstacle_view.get_obstacle_image()
            if obstacle_image is not None:
                self.image_state.main_image = obstacle_image
                return obstacle_image

        if self.context.shared.camera_mode == CameraModes.MAP_VIEW:
            # if the vacuum is working, or it is the first image.

            _ = await self._update_vacuum_state()
            if _ != "docked" or self.is_streaming:
                self.context.shared.image_grab = True
                self.context.shared.frame_number = (
                    self.processors.processor.get_frame_number()
                )
                # Record the time when we receive image data
                self._attr_frame_interval = FRAME_INTERVAL_S

            parsed_json, _, data_type = await self._process_parsed_json()

            if parsed_json is not None:
                if not self.context.shared.destinations and data_type == "Rand256":
                    self.context.shared.destinations = (
                        self.mqtt.connector.get_destinations()
                    )
                try:
                    await asyncio.wait_for(
                        self.processors.processor.run_process_valetudo_data(
                            parsed_json
                        ),
                        timeout=RENDER_TIMEOUT_S,
                    )
                except asyncio.TimeoutError:
                    LOGGER.warning("%s: Time out in rendering!", self.context.file_name)
                    return self.camera_image(
                        self.image_state.width, self.image_state.height
                    )
        return self.camera_image(self.image_state.width, self.image_state.height)

    async def _process_parsed_json(self, test_mode: bool = False):
        """Process the parsed JSON data and return the generated image."""
        if test_mode:
            LOGGER.debug("Camera Test Mode Active...")
            data_type = "hypfer"
            if not self.context.shared.image_grab:
                return None, test_mode, data_type
            if self.image_state.json_data is None:
                self.image_state.json_data = await async_load_file(
                    file_to_load="custom_components/mqtt_vacuum_camera/logs_formatter/test.json",
                    is_json=True,
                )
            parsed_json = self.image_state.json_data
            self.context.shared.camera_mode = CameraModes.MAP_VIEW
            return parsed_json, test_mode, data_type

        # Get data from MQTT and decompress it
        parsed_json = None
        payload, data_type = await self.mqtt.connector.update_data(
            self.context.shared.image_grab
        )
        if payload and data_type:
            data = payload.payload if hasattr(payload, "payload") else payload
            parsed_json = await self.context.hass.async_create_task(
                self.processors.decompression.decompress(
                    payload=data, data_type=data_type
                )
            )
        return parsed_json, test_mode, data_type

    def _pil_to_bytes(self, pil_img, image_id: str | None = None) -> Optional[bytes]:
        """Convert PIL image to bytes"""
        if pil_img:
            LOGGER.debug(
                "%s: Output Image: %s.",
                self.context.file_name,
                image_id if image_id else self.context.shared.vac_json_id,
            )
        else:
            if self.context.shared.last_image is not None:
                LOGGER.debug("%s: Using shared last_image.", self.context.file_name)
                pil_img = self.context.shared.last_image
        self.image_state.width = pil_img.width
        self.image_state.height = pil_img.height
        buffered = BytesIO()
        try:
            pil_img.save(buffered, format="PNG")
            return buffered.getvalue()
        finally:
            buffered.close()

    async def _run_async_pil_to_bytes(self, pil_img, image_id: str | None = None):
        """Thread function to process the image data using persistent thread pool."""
        try:
            result = await self.processors.thread_pool.run_in_executor(
                "camera_processing",
                self._pil_to_bytes,
                pil_img,
                image_id,
            )
            return result
        except (OSError, IOError) as e:
            LOGGER.error("Error encoding image to PNG: %s", str(e), exc_info=True)
            return None
        except (AttributeError, ValueError) as e:
            LOGGER.error("Invalid image data: %s", str(e), exc_info=True)
            return None
        except RuntimeError as e:
            LOGGER.error("Thread pool error: %s", str(e), exc_info=True)
            return None

    async def handle_vacuum_start(self, event):
        """Handle the event_vacuum_start event."""
        if event.data:
            self.context.shared.reset_trims()  # requires valetudo_map_parser >0.1.9b41

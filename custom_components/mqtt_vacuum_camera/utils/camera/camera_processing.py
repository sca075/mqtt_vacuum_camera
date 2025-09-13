"""
Multiprocessing module
Version: 2025.9.0
This module provide the image multiprocessing in order to
avoid the overload of the main_thread of Home Assistant.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from datetime import timedelta
from io import BytesIO
import time
from typing import Any

from PIL import Image
import aiohttp
from aiohttp.abc import HTTPException
from homeassistant.helpers.event import async_track_time_interval
from valetudo_map_parser.config.types import JsonType, PilPNG
from valetudo_map_parser.hypfer_handler import HypferMapImageHandler
from valetudo_map_parser.rand256_handler import ReImageHandler

from custom_components.mqtt_vacuum_camera.const import (
    LOGGER,
    NOT_STREAMING_STATES,
    CameraModes,
)
from custom_components.mqtt_vacuum_camera.utils.connection.connector import (
    ValetudoConnector,
)
from custom_components.mqtt_vacuum_camera.utils.connection.decompress import (
    DecompressionManager,
)
from custom_components.mqtt_vacuum_camera.utils.thread_pool import ThreadPoolManager

LOGGER.propagate = True


class CameraProcessor:
    """CameraProcessor class to process the image data from the Vacuum Json data."""

    def __init__(
        self,
        hass,
        camera_shared,
        thread_pool: ThreadPoolManager,
        connector: ValetudoConnector,
    ):
        self.hass = hass
        self._map_handler = HypferMapImageHandler(camera_shared)
        self._re_handler = ReImageHandler(camera_shared)
        self._shared = camera_shared
        self._thread_pool = thread_pool
        self._file_name = self._shared.file_name
        self.processing_time = 3.0
        self.is_processing = False
        self._connector = connector
        self._dm = DecompressionManager.get_instance(self._file_name)
        self._busy_lock = asyncio.Lock()
        self._unsub_update = async_track_time_interval(
            self.hass,
            self.async_handler_update,
            timedelta(seconds=3),
            name=f"{self._file_name}_CameraProcessor",
            cancel_on_shutdown=True,
        )

    async def async_shutdown(self) -> None:
        """Cancel the scheduled update timer (and any subscriptions) when unloading."""
        if getattr(self, "_unsub_update", None):
            self._unsub_update()
            self._unsub_update = None

    async def _update_vacuum_state(self):
        """Update vacuum state based on MQTT data."""
        self._shared.vacuum_battery = await self._connector.get_battery_level()
        self._shared.vacuum_connection = (
            await self._connector.get_vacuum_connection_state()
        )

        if not self._shared.vacuum_connection:
            self._shared.vacuum_state = "disconnected"
        else:
            if self._shared.vacuum_state == "disconnected":
                self._shared.vacuum_state = await self._connector.get_vacuum_status()
            else:
                self._shared.vacuum_state = await self._connector.get_vacuum_status()
        return self._shared.vacuum_state

    async def async_handler_update(self, now):
        """Scheduled processing tick: ensure grab flags and process latest payload if any."""
        # busy lock skip
        if self._busy_lock.locked():
            return
        # Check if we need to process data
        state = await self._update_vacuum_state()
        if (state not in NOT_STREAMING_STATES) and not self.is_processing:
            LOGGER.debug("%s: async_handler_update condition met. %s", self._file_name, state)
            self.is_processing = True
            self._shared.image_grab = True
            self._shared.frame_number = self.get_frame_number()
        else:
            self.is_processing = False
            return

        async with self._busy_lock:
            LOGGER.debug("%s: async_handler_update", self._file_name)
            # Only process in map view
            if self._shared.camera_mode != CameraModes.MAP_VIEW:
                return
            # Quick exit if no data signaled
            if not self._connector.is_data_available():
                return
            start_time = time.perf_counter()
            payload, data_type = await self._connector.update_data(
                self._shared.image_grab
            )
            if not payload or not data_type:
                return
            LOGGER.debug("%s: Processing image data.", self._file_name)

            data = payload.payload if hasattr(payload, "payload") else payload
            parsed = await self._dm.decompress(self._file_name, data, data_type)
            if parsed is None:
                return
            else:
                _ = await self.run_process_valetudo_data(parsed)
                del parsed
            self.processing_time = round(time.perf_counter() - start_time, 2)
            LOGGER.debug(
                "%s: Image processing complete in %r seconds.",
                self._file_name,
                self.processing_time,
            )

    async def async_process_valetudo_data(self, parsed_json: JsonType) -> PilPNG | None:
        """Compose the Camera Image from the Vacuum Json data."""
        if parsed_json is None:
            LOGGER.debug("%s: No Json, returned None.", self._file_name)
            return None

        pil_img = await self._map_handler.async_get_image(
            m_json=parsed_json, bytes_format=True
        )

        if pil_img is not None:
            if self._shared.map_rooms is None:
                self._shared.map_rooms = (
                    await self._map_handler.async_get_rooms_attributes()
                )
                if self._shared.map_rooms:
                    LOGGER.debug("%s: Attributes rooms updated", self._file_name)

            if self._shared.attr_calibration_points is None:
                self._shared.attr_calibration_points = (
                    self._map_handler.get_calibration_data()
                )

            self._shared.vac_json_id = self._map_handler.get_json_id()

            if not self._shared.charger_position:
                self._shared.charger_position = self._map_handler.get_charger_position()

            self._shared.current_room = self._map_handler.get_robot_position()
            self._shared.map_rooms = self._map_handler.room_propriety

            if not self._shared.image_size:
                self._shared.image_size = self._map_handler.get_img_size()

            if not self._shared.snapshot_take and (
                self._shared.vacuum_state in NOT_STREAMING_STATES
            ):
                if self._shared.frame_number != self._map_handler.get_frame_number():
                    self._shared.image_grab = False
                    LOGGER.info(
                        "Suspended the camera data processing for: %s.",
                        self._file_name,
                    )
                    self._shared.image_grab = False
        return pil_img

    async def async_process_rand256_data(self, parsed_json: JsonType) -> PilPNG | None:
        """Process the image data from the RAND256 Json data."""
        if parsed_json is None:
            return None

        pil_img = await self._re_handler.async_get_image(
            m_json=parsed_json,
            destinations=self._shared.destinations,
            bytes_format=True,
        )

        if pil_img is not None:
            if self._shared.map_rooms is None and self._shared.destinations:
                (
                    self._shared.map_rooms,
                    self._shared.map_pred_zones,
                    self._shared.map_pred_points,
                ) = await self._re_handler.get_rooms_attributes(
                    self._shared.destinations
                )
                if self._shared.map_rooms:
                    LOGGER.debug("%s: State attributes rooms updated", self._file_name)

            if self._shared.attr_calibration_points is None:
                self._shared.attr_calibration_points = (
                    self._re_handler.get_calibration_data(self._shared.image_rotate)
                )

            self._shared.vac_json_id = self._re_handler.get_json_id()

            if not self._shared.charger_position:
                self._shared.charger_position = self._re_handler.get_charger_position()

            self._shared.current_room = self._re_handler.get_robot_position()

            if not self._shared.image_size:
                self._shared.image_size = self._re_handler.get_img_size()

            if not self._shared.snapshot_take and (
                self._shared.vacuum_state in NOT_STREAMING_STATES
            ):
                LOGGER.info(
                    "Suspended the camera data processing for: %s.", self._file_name
                )
                self._shared.snapshot_take = True
                self._shared.image_grab = False

        return pil_img

    def run_process_valetudo_data(self, parsed_json: JsonType):
        """Process the image data from the Vacuum Json data (run in executor)."""
        try:
            if self._shared.is_rand:
                # Ensure Rand256 destinations only once
                if not self._shared.destinations:
                    self._shared.destinations = self._connector.get_destinations()
                return self._thread_pool.run_async_in_executor(
                    "camera_processing", self.async_process_rand256_data, parsed_json
                )
            else:
                return self._thread_pool.run_async_in_executor(
                    "camera_processing", self.async_process_valetudo_data, parsed_json
                )
        except RuntimeError as e:
            LOGGER.error("Error processing image data: %s", str(e), exc_info=True)
            return None

    def get_frame_number(self):
        """Get the frame number."""
        return self._map_handler.get_frame_number() - 2

    @staticmethod
    async def download_image(url: str, set_timeout: int = 6):
        """Asynchronously download an image without blocking."""
        try:
            timeout = aiohttp.ClientTimeout(total=set_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        obstacle_image = await response.read()
                        LOGGER.debug("Image downloaded successfully!")
                        return obstacle_image
                    raise HTTPException(
                        text="Failed to download the Obstacle image.",
                        reason=response.reason,
                    )
        except aiohttp.ClientError as e:
            LOGGER.warning("Timeout error occurred: %s", e, exc_info=True)
            return None
        except asyncio.TimeoutError as e:
            LOGGER.error("Error downloading image: %s", e, exc_info=True)
            return None

    async def async_open_image(self, obstacle_image: Any) -> Image.Image:
        """Asynchronously open an image file using a thread pool."""
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=f"{self._file_name}_camera"
        )
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, Image.open, BytesIO(obstacle_image))

"""
Multiprocessing module
Version: 2025.5.0
This module provide the image multiprocessing in order to
avoid the overload of the main_thread of Home Assistant.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import time
from io import BytesIO
from typing import Any, Optional

from PIL import Image
import aiohttp
from aiohttp.abc import HTTPException
from valetudo_map_parser.config.drawable import Drawable as Draw
from valetudo_map_parser.config.types import Color, JsonType, PilPNG
from valetudo_map_parser.hypfer_handler import HypferMapImageHandler
from valetudo_map_parser.rand25_handler import ReImageHandler
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send,
    async_dispatcher_connect,
)

from custom_components.mqtt_vacuum_camera.const import (
    DOMAIN,
    LOGGER,
    NOT_STREAMING_STATES,
)
from custom_components.mqtt_vacuum_camera.utils.files_operations import (
    async_get_active_user_language,
)
from custom_components.mqtt_vacuum_camera.utils.status_text import StatusText
from custom_components.mqtt_vacuum_camera.utils.thread_pool import ThreadPoolManager

LOGGER.propagate = True


class CameraProcessor:
    """
    CameraProcessor class to process the image data from the Vacuum Json data.
    """

    def __init__(
        self,
        hass,
        camera_shared,
        decompression_manager=None,
        connector=None,
        coordinator=None,
    ):
        self.hass = hass
        self._map_handler = HypferMapImageHandler(camera_shared)
        self._re_handler = ReImageHandler(camera_shared)
        self._shared = camera_shared
        self._file_name = self._shared.file_name
        self._thread_pool = ThreadPoolManager(self._file_name)
        self._translations_path = self.hass.config.path(
            "custom_components/mqtt_vacuum_camera/translations/"
        )
        self._status_text = StatusText(self.hass, self._shared)
        self._decompression_manager = decompression_manager
        self._connector = connector
        self._coordinator = coordinator  # Reference to coordinator for notifications

        # Image caching
        self.current_image = None
        self.current_image_bytes = None
        self.current_image_hash = None
        self._last_image = None
        self._last_image_time: Optional[datetime] = None

        # Simple storage
        self._processing_lock = False
        self._processing_time = 0
        self.camera_streaming = False

        self._unsub_dispatcher = async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{self._file_name}_camera_update",
            self.async_handle_mqtt_camera_update,
        )

    async def async_process_valetudo_data(self, parsed_json: JsonType) -> PilPNG | None:
        """
        Compose the Camera Image from the Vacuum Json data.
        :param parsed_json:
        :return pil_img:
        """
        if parsed_json is not None:
            pil_img = await self._map_handler.async_get_image_from_json(
                m_json=parsed_json,
            )

            if self._shared.export_svg:
                self._shared.export_svg = False

            if pil_img is not None:
                if self._shared.map_rooms is None:
                    self._shared.map_rooms = (
                        await self._map_handler.async_get_rooms_attributes()
                    )
                    if self._shared.map_rooms:
                        LOGGER.debug(
                            "%s: State attributes rooms updated", self._file_name
                        )

                if self._shared.attr_calibration_points is None:
                    self._shared.attr_calibration_points = (
                        self._map_handler.get_calibration_data()
                    )

                self._shared.vac_json_id = self._map_handler.get_json_id()

                if not self._shared.charger_position:
                    self._shared.charger_position = (
                        self._map_handler.get_charger_position()
                    )

                self._shared.current_room = self._map_handler.get_robot_position()
                self._shared.map_rooms = self._map_handler.room_propriety
                if self._shared.map_rooms:
                    LOGGER.debug("%s: State attributes rooms updated", self._file_name)
                if not self._shared.image_size:
                    self._shared.image_size = self._map_handler.get_img_size()

                updated_vac_state = self._shared.vacuum_state
                if not self._shared.snapshot_take and (
                    updated_vac_state in NOT_STREAMING_STATES
                ):
                    # suspend image processing if we are at the next frame.
                    if (
                        self._shared.frame_number
                        != self._map_handler.get_frame_number()
                    ):
                        self._shared.image_grab = False
                        LOGGER.info(
                            "Set the camera data processing for: %s to %s.",
                            self._file_name,
                            self._shared.image_grab,
                        )
                        # take a snapshot
                        self._shared.snapshot_take = True
            return pil_img
        LOGGER.debug("%s: No Json, returned None.", self._file_name)
        return None

    async def async_process_rand256_data(self, parsed_json: JsonType) -> PilPNG | None:
        """
        Process the image data from the RAND256 Json data.
        :param parsed_json:
        :return: pil_img
        """
        if parsed_json is not None:
            pil_img = await self._re_handler.get_image_from_rrm(
                m_json=parsed_json,
                destinations=self._shared.destinations,
            )

            if pil_img is not None:
                if self._shared.map_rooms is None:
                    destinations = self._shared.destinations
                    if destinations is not None:
                        (
                            self._shared.map_rooms,
                            self._shared.map_pred_zones,
                            self._shared.map_pred_points,
                        ) = await self._re_handler.get_rooms_attributes(destinations)
                    if self._shared.map_rooms:
                        LOGGER.debug(
                            "%s: State attributes rooms updated", self._file_name
                        )

                if self._shared.attr_calibration_points is None:
                    self._shared.attr_calibration_points = (
                        self._re_handler.get_calibration_data(self._shared.image_rotate)
                    )

                self._shared.vac_json_id = self._re_handler.get_json_id()

                if not self._shared.charger_position:
                    self._shared.charger_position = (
                        self._re_handler.get_charger_position()
                    )
                self._shared.current_room = self._re_handler.get_robot_position()
                if not self._shared.image_size:
                    self._shared.image_size = self._re_handler.get_img_size()

                update_vac_state = self._shared.vacuum_state
                if not self._shared.snapshot_take and (
                    update_vac_state in NOT_STREAMING_STATES
                ):
                    # suspend image processing if we are at the next frame.
                    LOGGER.info(
                        "Suspended the camera data processing for: %s.", self._file_name
                    )
                    # take a snapshot
                    self._shared.snapshot_take = True
                    self._shared.image_grab = False
            return pil_img
        return None

    async def run_async_process_valetudo_data(
        self, parsed_json: JsonType
    ) -> PilPNG | None:
        """Thread function to process the image data using ThreadPoolManager."""
        if self._shared.is_rand:
            result = await self._thread_pool.run_async_in_executor(
                "camera_processing",
                self.async_process_rand256_data,  # sync function!
                parsed_json,
            )
        else:
            result = await self._thread_pool.run_async_in_executor(
                "camera_processing",
                self.async_process_valetudo_data,  # sync function!
                parsed_json,
            )
        return result

    def get_frame_number(self):
        """Get the frame number."""
        return self._map_handler.get_frame_number() - 2

    # Functions to Thread the image text processing.
    async def async_draw_image_text(
        self, pil_img: PilPNG, color: Color, font: str, img_top: bool = True
    ) -> PilPNG:
        """Draw text on the image."""
        if self._shared.user_language is None:
            self._shared.user_language = await async_get_active_user_language(self.hass)
        if pil_img is not None:
            text, size = await self._status_text.async_get_status_text(pil_img)
            Draw.status_text(
                image=pil_img,
                size=size,
                color=color,
                status=text,
                path_font=font,
                position=img_top,
            )
        return pil_img

    @staticmethod
    async def download_image(url: str, set_timeout: int = 6):
        """
        Asynchronously download an image without blocking.

        Args:
            url (str): The URL to download the image from.
            set_timeout (int): The timeout for the download in seconds.
        Returns:
            Image: The downloaded image in jpeg format.
        """

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
                        reason=response.reason or "Unknown server error",
                    )
        except aiohttp.ClientError as e:
            LOGGER.warning(
                "Timeout error occurred: %s",
                e,
                exc_info=True,
            )
            return None
        except asyncio.TimeoutError as e:
            LOGGER.error("Error downloading image: %s", e, exc_info=True)
            return None

    # noinspection PyTypeChecker
    async def async_open_image(self, obstacle_image: Any) -> Image.Image:
        """
        Asynchronously open an image file using a thread pool.
        Args:
            obstacle_image (Any): image file bytes or jpeg format.

        Returns:
            Image.Image: PIL image.
        """
        pil_img = await self._thread_pool.run_in_executor(
            "camera", Image.open, BytesIO(obstacle_image)
        )
        return pil_img

    async def async_handle_mqtt_camera_update(self):
        """Handle the event_vacuum_start event."""
        if self._processing_lock:
            LOGGER.debug("Processing lock active, skipping update")
            return
        start_time = time.perf_counter()
        LOGGER.info("Received Connector Update, starting processing")
        if self._shared.is_rand and not self._shared.destinations:
            self._shared.destinations = await self._connector.get_destinations()

        payload, data_type = await self._connector.update_data(True)
        if payload and data_type:
            (
                self.current_image_bytes,
                self.current_image,
            ) = await self.async_process_image_data(payload, data_type)
            end_time = time.perf_counter()
            self._processing_time = round(end_time - start_time, 2)
            LOGGER.debug(
                "%s: Image processing time: %r seconds",
                self._file_name,
                self._processing_time,
            )
            async_dispatcher_send(
                self.hass,
                f"{DOMAIN}_{self._file_name}_camera_update_ready",
            )

    async def async_process_image_data(self, payload, data_type: str):
        """Process image data - simple and direct."""
        try:
            # Decompress data
            self._processing_lock = True
            parsed_json = None
            if self._decompression_manager:
                data = payload.payload if hasattr(payload, "payload") else payload
                parsed_json = await self._decompression_manager.decompress(
                    data, data_type
                )
            if not parsed_json:
                LOGGER.debug(
                    "No JSON data after decompression for: %s", self._file_name
                )
                return self.current_image_bytes, self.current_image

            # Process image
            pil_image = await self.run_async_process_valetudo_data(parsed_json)

            if pil_image:
                # Store PIL image
                self.current_image = pil_image
                # Convert to bytes and store
                self.current_image_bytes = (
                    await self._thread_pool.run_async_in_executor(
                        "camera",
                        self._async_pil_to_bytes,
                        pil_image,
                    )
                )
                # self._async_pil_to_bytes(pil_image)
                LOGGER.debug(
                    "Image processed and bytes stored for: %s", self._file_name
                )
            else:
                LOGGER.debug("No PIL image generated for: %s", self._file_name)

        except Exception as err:
            LOGGER.error(
                "Error processing image data for %s: %s",
                self._file_name,
                err,
                exc_info=True,
            )
        return self.current_image_bytes, self.current_image

    async def _async_pil_to_bytes(self, pil_img, image_id: str = None):
        """Convert PIL image to bytes - copied from entity logic."""
        pil_img_text = None

        if pil_img:
            LOGGER.debug(
                "%s: Converting PIL to bytes: %s",
                self._file_name,
                image_id
                if image_id
                else getattr(self._shared, "vac_json_id", "unknown"),
            )

            # Add status text if enabled
            if getattr(self._shared, "show_vacuum_state", False):
                pil_img_text = await self.async_draw_image_text(
                    pil_img,
                    self._shared.user_colors[8],
                    self._shared.vacuum_status_font,
                    self._shared.vacuum_status_position,
                )
        else:
            if self._last_image is not None:
                pil_img = self._last_image.copy()
            else:
                pil_img = Image.new("RGB", (800, 600), "gray")

        self._last_image_time = datetime.now()
        buffered = BytesIO()

        try:
            if pil_img_text:
                pil_img_text.save(buffered, format="PNG")
            else:
                pil_img.save(buffered, format="PNG")
            return buffered.getvalue()
        except Exception as err:
            LOGGER.error(
                "Error converting PIL to bytes for %s: %s", self._file_name, err
            )
            return None
        finally:
            buffered.close()

    def get_image_bytes(self) -> Optional[bytes]:
        """Get current image bytes - simple sync function."""
        return self.current_image_bytes

    def get_current_pil_image(self) -> Optional[Image.Image]:
        """Get current PIL image."""
        return self.current_image

    def get_processing_time(self):
        """Get the processing time."""
        return self._processing_time

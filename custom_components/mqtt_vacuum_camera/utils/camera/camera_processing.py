"""
Multiprocessing module
Version: 2025.3.0b1
This module provide the image multiprocessing in order to
avoid the overload of the main_thread of Home Assistant.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from io import BytesIO
from typing import Any

from PIL import Image
import aiohttp
from aiohttp.abc import HTTPException
from valetudo_map_parser.config.types import JsonType, PilPNG
from valetudo_map_parser.hypfer_handler import HypferMapImageHandler
from valetudo_map_parser.rand256_handler import ReImageHandler

from custom_components.mqtt_vacuum_camera.const import LOGGER, NOT_STREAMING_STATES
from custom_components.mqtt_vacuum_camera.utils.thread_pool import ThreadPoolManager

LOGGER.propagate = True


class CameraProcessor:
    """
    CameraProcessor class to process the image data from the Vacuum Json data.
    """

    def __init__(self, hass, camera_shared, thread_pool: ThreadPoolManager):
        self.hass = hass
        self._map_handler = HypferMapImageHandler(camera_shared)
        self._re_handler = ReImageHandler(camera_shared)
        self._shared = camera_shared
        self._thread_pool = thread_pool
        self.data = {}
        self._file_name = self._shared.file_name

    async def async_process_valetudo_data(self, parsed_json: JsonType) -> PilPNG | None:
        """
        Compose the Camera Image from the Vacuum Json data.
        :param parsed_json:
        :return pil_img:
        """
        if parsed_json is not None:
            pil_img, data = await self._map_handler.async_get_image(
                m_json=parsed_json, bytes_format=True
            )

            if self._shared.export_svg:
                self._shared.export_svg = False

            if pil_img is not None:
                self.data = data
                update_vac_state = self._shared.vacuum_state
                if not self._shared.snapshot_take and (
                    update_vac_state in NOT_STREAMING_STATES
                ):
                    # suspend image processing if we are at the next frame.
                    if (
                        self._shared.frame_number
                        != self._map_handler.get_frame_number()
                    ):
                        self._shared.image_grab = False
            return pil_img
        return None

    async def async_process_rand256_data(self, parsed_json: JsonType) -> PilPNG | None:
        """
        Process the image data from the RAND256 Json data.
        :param parsed_json:
        :return: pil_img
        """
        if parsed_json is not None:
            pil_img, data = await self._re_handler.async_get_image(
                m_json=parsed_json,
                destinations=self._shared.destinations,
                bytes_format=True,
            )
            if pil_img is not None:
                self.data = data
                update_vac_state = self._shared.vacuum_state
                if not self._shared.snapshot_take and (
                    update_vac_state in NOT_STREAMING_STATES
                ):
                    # suspend image processing if we are at the next frame.
                    self._shared.image_grab = False
            return pil_img
        return None

    def run_process_valetudo_data(self, parsed_json: JsonType):
        """Async function to process the image data from the Vacuum Json data."""
        try:
            if self._shared.is_rand:
                result = self._thread_pool.run_async_in_executor(
                    "camera_processing",
                    self.async_process_rand256_data,
                    parsed_json,
                )
            else:
                result = self._thread_pool.run_async_in_executor(
                    "camera_processing",
                    self.async_process_valetudo_data,
                    parsed_json,
                )
        except RuntimeError as e:
            LOGGER.error("Error processing image data: %s", str(e), exc_info=True)
            return None

        return result

    def get_frame_number(self):
        """Get the frame number."""
        return self._map_handler.get_frame_number() - 2

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
                        return obstacle_image
                    raise HTTPException(
                        text="Failed to download the Obstacle image.",
                        reason=response.reason,
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

    async def async_open_image(self, obstacle_image: Any) -> Image.Image:
        """Asynchronously open an image file using a temporary 1-worker pool."""

        def open_image(image_data: Any) -> Image.Image:
            return Image.open(BytesIO(image_data))

        # obstacle_image
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=f"{self._file_name}_camera"
        ) as ex:
            fut = ex.submit(open_image, obstacle_image)
            result = await asyncio.wrap_future(fut)
        return result

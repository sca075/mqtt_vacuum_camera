"""
Multiprocessing module
Version: 2026.3.1
This module provide the image multiprocessing in order to
avoid the overload of the main_thread of Home Assistant.
"""

from __future__ import annotations

import asyncio
from io import BytesIO
from typing import Any

from PIL import Image
import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from valetudo_map_parser.config.types import JsonType
from valetudo_map_parser.conga_handler import CongaMapImageHandler
from valetudo_map_parser.hypfer_handler import HypferMapImageHandler
from valetudo_map_parser.rand256_handler import ReImageHandler

from custom_components.mqtt_vacuum_camera.const import LOGGER, NOT_STREAMING_STATES
from custom_components.mqtt_vacuum_camera.utils.thread_pool import ThreadPoolManager

LOGGER.propagate = True


class CameraProcessor:
    """
    CameraProcessor class to process the image data from the Vacuum JSON data.
    """

    def __init__(self, hass, camera_shared, thread_pool: ThreadPoolManager):
        self.hass = hass
        self._shared = camera_shared
        if self._shared.is_rand:
            self._handler = ReImageHandler(camera_shared)
        elif self._shared.is_conga:
            self._handler = CongaMapImageHandler(camera_shared)
        else:
            self._handler = HypferMapImageHandler(camera_shared)
        self._thread_pool = thread_pool
        self.data: dict[str, Any] = {}
        self._file_name = self._shared.file_name

    async def async_process_image_data(
        self, parsed_json: JsonType
    ) -> Image.Image | bytes | None:
        """
        Compose the Camera Image from the Vacuum JSON data.
        :param parsed_json: Parsed JSON data from vacuum
        :return: PIL image, bytes, or None
        """
        if parsed_json is None:
            return None

        if self._shared.is_rand:
            pil_img, data = await self._handler.async_get_image(
                m_json=parsed_json,
                destinations=self._shared.destinations,
                bytes_format=True,
            )
        else:
            pil_img, data = await self._handler.async_get_image(
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
                if self._shared.is_rand:
                    self._shared.image_grab = False
                    self._handler.update_trims()
                else:
                    if self._shared.frame_number != self._handler.get_frame_number():
                        self._shared.image_grab = False
                        self._handler.update_trims()
        return pil_img

    def run_process_valetudo_data(self, parsed_json: JsonType):
        """Schedule async processing of image data from the Vacuum JSON data."""
        try:
            result = self._thread_pool.run_async_in_executor(
                "camera_processing",
                self.async_process_image_data,
                parsed_json,
            )
        except RuntimeError as e:
            LOGGER.error("Error processing image data: %s", str(e), exc_info=True)
            return None

        return result

    def get_frame_number(self):
        """Get the frame number."""
        if self._shared.is_rand:
            return self._handler.get_frame_number()
        return self._handler.get_frame_number() - 2

    async def download_image(self, url: str, set_timeout: int = 6):
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
            session = async_get_clientsession(self.hass)
            async with session.get(url, timeout=timeout) as response:
                if response.status == 200:
                    return await response.read()
                LOGGER.warning(
                    "Failed to download obstacle image. Status: %s, Reason: %s",
                    response.status,
                    response.reason,
                )
                return None
        except aiohttp.ClientError as e:
            LOGGER.warning(
                "Client error occurred: %s",
                e,
                exc_info=True,
            )
            return None
        except TimeoutError as e:
            LOGGER.warning("Timeout downloading image: %s", e)
            return None

    async def async_open_image(self, obstacle_image: Any) -> Image.Image:
        """Asynchronously open an image without blocking the event loop."""

        def open_image(image_data: Any) -> Image.Image:
            return Image.open(BytesIO(image_data))

        return await asyncio.to_thread(open_image, obstacle_image)

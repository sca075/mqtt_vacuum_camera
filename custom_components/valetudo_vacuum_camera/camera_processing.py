"""
Multiprocessing module
Version: v2024.06.0
This module provide the image multiprocessing in order to
avoid the overload of the main_thread of Home Assistant.
"""

from __future__ import annotations

import asyncio
from asyncio import gather, get_event_loop
import concurrent.futures
import logging

from .types import Color, JsonType, PilPNG
from .utils.drawable import Drawable as Draw
from .utils.status_text import StatusText
from .utils.users_data import async_get_active_user_language
from .valetudo.hypfer.image_handler import MapImageHandler
from .valetudo.rand256.image_handler import ReImageHandler

_LOGGER: logging.Logger = logging.getLogger(__name__)
_LOGGER.propagate = True


class CameraProcessor:
    """
    CameraProcessor class to process the image data from the Vacuum Json data.
    """

    def __init__(self, hass, camera_shared):
        self.hass = hass
        self._map_handler = MapImageHandler(camera_shared)
        self._re_handler = ReImageHandler(camera_shared)
        self._shared = camera_shared
        self._file_name = self._shared.file_name
        self._translations_path = self.hass.config.path(
            "custom_components/valetudo_vacuum_camera/translations/"
        )
        self._status_text = StatusText(self.hass, self._shared)

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
                        _LOGGER.debug(
                            f"\n{self._file_name}: State attributes rooms updated"
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

                if not self._shared.image_size:
                    self._shared.image_size = self._map_handler.get_img_size()

                if not self._shared.snapshot_take and (
                    self._shared.vacuum_state == "idle"
                    or self._shared.vacuum_state == "docked"
                    or self._shared.vacuum_state == "error"
                ):
                    # suspend image processing if we are at the next frame.
                    if (
                        self._shared.frame_number
                        != self._map_handler.get_frame_number()
                    ):
                        self._shared.image_grab = False
                        _LOGGER.info(
                            f"\nSuspended the camera data processing for: {self._file_name}."
                        )
                        # take a snapshot
                        self._shared.snapshot_take = True
            return pil_img
        _LOGGER.debug(f"\n{self._file_name}: No Json, returned None.")
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
                        _LOGGER.debug(
                            f"\n{self._file_name}: State attributes rooms updated"
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

                if not self._shared.snapshot_take and (
                    self._shared.vacuum_state == "idle"
                    or self._shared.vacuum_state == "docked"
                    or self._shared.vacuum_state == "error"
                ):
                    # suspend image processing if we are at the next frame.
                    _LOGGER.info(
                        f"\nSuspended the camera data processing for: {self._file_name}."
                    )
                    # take a snapshot
                    self._shared.snapshot_take = True
                    self._shared.image_grab = False
            return pil_img
        return None

    def process_valetudo_data(self, parsed_json: JsonType):
        """Async function to process the image data from the Vacuum Json data."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if self._shared.is_rand:
                result = loop.run_until_complete(
                    self.async_process_rand256_data(parsed_json)
                )
            else:
                result = loop.run_until_complete(
                    self.async_process_valetudo_data(parsed_json)
                )
        finally:
            loop.close()
        return result

    async def run_async_process_valetudo_data(
        self, parsed_json: JsonType
    ) -> PilPNG | None:
        """Thread function to process the image data from the Vacuum Json data."""
        num_processes = 1
        parsed_json_list = [parsed_json for _ in range(num_processes)]
        loop = get_event_loop()

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=f"{self._file_name}_camera"
        ) as executor:
            tasks = [
                loop.run_in_executor(executor, self.process_valetudo_data, parsed_json)
                for parsed_json in parsed_json_list
            ]
            images = await gather(*tasks)

        if isinstance(images, list) and len(images) > 0:
            _LOGGER.debug(f"\n{self._file_name}: Camera frame processed.")
            result = images[0]
        else:
            result = None

        return result

    def get_frame_number(self):
        """Get the frame number."""
        return self._map_handler.get_frame_number() - 2

    """
    Functions to Thread the image text processing.
    """

    async def async_draw_image_text(
        self, pil_img: PilPNG, color: Color, font: str, img_top: bool = True
    ) -> PilPNG:
        """Draw text on the image."""
        if self._shared.user_language is None:
            self._shared.user_language = await async_get_active_user_language(self.hass)
        if pil_img is not None:
            text, size = self._status_text.get_status_text(pil_img)
            Draw.status_text(
                image=pil_img,
                size=size,
                color=color,
                status=text,
                path_font=font,
                position=img_top,
            )
        return pil_img

    def process_status_text(
        self, pil_img: PilPNG, color: Color, font: str, img_top: bool = True
    ):
        """Async function to process the image data from the Vacuum Json data."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                self.async_draw_image_text(pil_img, color, font, img_top)
            )
        finally:
            loop.close()
        return result

    async def run_async_draw_image_text(self, pil_img: PilPNG, color: Color) -> PilPNG:
        """Thread function to process the image data from the Vacuum Json data."""
        num_processes = 1
        pil_img_list = [pil_img for _ in range(num_processes)]
        loop = get_event_loop()

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=f"{self._file_name}_camera_text"
        ) as executor:
            tasks = [
                loop.run_in_executor(
                    executor,
                    self.process_status_text,
                    pil_img,
                    color,
                    self._shared.vacuum_status_font,
                    self._shared.vacuum_status_position,
                )
                for pil_img in pil_img_list
            ]
            images = await gather(*tasks)

        if isinstance(images, list) and len(images) > 0:
            result = images[0]
        else:
            result = None

        return result

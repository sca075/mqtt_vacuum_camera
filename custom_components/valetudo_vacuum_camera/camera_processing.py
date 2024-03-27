"""
Multiprocessing module
Version: v2024.04
This module provide the image multiprocessing in order to
avoid the overload of the main_thread of Home Assistant.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
from asyncio import gather, get_event_loop

from .types import Color, JsonType, PilPNG
from .utils.drawable import Drawable as Draw
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
                        _LOGGER.debug("State attributes rooms updated")

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
                            f"Suspended the camera data processing for: {self._shared.file_name}."
                        )
                        # take a snapshot
                        self._shared.snapshot_take = True
            return pil_img
        _LOGGER.debug("No Json, returned None.")
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
                        _LOGGER.debug("State attributes rooms updated")

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
                        f"Suspended the camera data processing for: {self._shared.file_name}."
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
            max_workers=1, thread_name_prefix=f"{self._shared.file_name}_camera"
        ) as executor:
            tasks = [
                loop.run_in_executor(executor, self.process_valetudo_data, parsed_json)
                for parsed_json in parsed_json_list
            ]
            images = await gather(*tasks)

        if isinstance(images, list) and len(images) > 0:
            _LOGGER.debug(f"{self._shared.file_name}: Camera frame processed.")
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

    def load_translations(self, language: str) -> JsonType:
        """
        Load the user selected language json file and return it.
        @param language:
        @return: json format
        """
        with open(f"{language}.json", "r") as file:
            translations = json.load(file)
        return translations

    def get_vacuum_status_translation(self, language: str) -> any:
        """
        Get the vacuum status translation.
        @param language: String IT, PL, DE, ES, FR, EN.
        @return: Json data or None.
        """
        translations = self.load_translations(language)
        if "vacuum_status" in translations:
            return translations["vacuum_status"]
        else:
            return None

    def get_status_text(self, text_img: PilPNG) -> tuple[list[str], int]:
        """
        Compose the image status text.
        :param text_img: Image to draw the text on.
        :return status_text, text_size: List of the status text and the text size.
        """
        status_text = ["If you read me, something went wrong.."]  # default text
        text_size_coverage = 1.5  # resize factor for the text
        text_size = self._shared.vacuum_status_size  # default text size
        charge_level = "\u03DE"  # unicode Koppa symbol
        charging = "\u2211"  # unicode Charging symbol
        if self._shared.show_vacuum_state:
            status_text = [
                f"{self._shared.file_name}: {self._shared.vacuum_state.capitalize()}"
            ]
            if not self._shared.vacuum_connection:
                status_text = [f"{self._shared.file_name}: Disconnected from MQTT?"]
            else:
                if self._shared.current_room:
                    try:
                        in_room = self._shared.current_room.get("in_room", None)
                    except (ValueError, KeyError):
                        _LOGGER.debug("No in_room data.")
                    else:
                        if in_room:
                            status_text.append(f" ({in_room})")
                if self._shared.vacuum_state == "docked":
                    if int(self._shared.vacuum_battery) <= 99:
                        status_text.append(f" \u00B7 ")
                        status_text.append(f"{charging}{charge_level} ")
                        status_text.append(f"{self._shared.vacuum_battery}%")
                        self._shared.vacuum_bat_charged = False
                    else:
                        status_text.append(f" \u00B7 ")
                        status_text.append(f"{charge_level} ")
                        status_text.append("Ready.")
                        self._shared.vacuum_bat_charged = True
                else:
                    status_text.append(f" \u00B7 ")
                    status_text.append(f"{charge_level}")
                    status_text.append(f" {self._shared.vacuum_battery}%")
                if text_size >= 50:
                    text_pixels = sum(len(text) for text in status_text)
                    text_size = int(
                        (text_size_coverage * text_img.width) // text_pixels
                    )
        return status_text, text_size

    async def async_draw_image_text(
        self, pil_img: PilPNG, color: Color, font: str, img_top: bool = True
    ) -> PilPNG:
        """Draw text on the image."""
        if pil_img is not None:
            text, size = self.get_status_text(pil_img)
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
            max_workers=1, thread_name_prefix=f"{self._shared.file_name}_camera_text"
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

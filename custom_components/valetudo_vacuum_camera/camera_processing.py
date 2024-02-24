"""
Multiprocessing module (version v1.5.9-beta.2)
This module provide the image multiprocessing in order to
avoid the overload of the main_thread of Home Assistant.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from asyncio import gather, get_event_loop

from .types import Color, PilPNG
from .utils.draweble import Drawable as Draw
from .valetudo.hypfer.image_handler import MapImageHandler
from .valetudo.valetudore.image_handler import ReImageHandler

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

    async def async_process_valetudo_data(self, parsed_json):
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

    async def async_process_rand256_data(self, parsed_json):
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
                if self._shared.show_vacuum_state:
                    self._re_handler.draw.status_text(
                        pil_img,
                        50,
                        self._shared.user_colors[8],
                        self._shared.file_name + ": " + self._shared.vacuum_state,
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
                        f"Suspended the camera data processing for: {self._shared.file_name}."
                    )
                    # take a snapshot
                    self._shared.snapshot_take = True
                    self._shared.image_grab = False
            return pil_img
        return None

    def process_valetudo_data(self, parsed_json):
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

    async def run_async_process_valetudo_data(self, parsed_json):
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
            _LOGGER.debug(
                f"{self._shared.file_name}: Got {len(images)} elements list.."
            )
            result = images[0]
        else:
            result = None

        return result

    def get_frame_number(self):
        """Get the frame number."""
        return self._map_handler.get_frame_number() - 2

    def get_status_text(self):
        """Get the status text."""
        status_text = "Something went wrong.."
        text_size = 50
        charge_level = u"\u2301"  # unicode Battery symbol
        charging = u"\u2211"  # unicode Charging symbol
        if self._shared.show_vacuum_state:
            status_text = f"{self._shared.file_name}: {self._shared.vacuum_state.upper()}"
            if not self._shared.vacuum_connection:
                status_text = f"{self._shared.file_name}: Disconnected from MQTT"
            else:
                if self._shared.current_room:
                    try:
                        in_room = self._shared.current_room.get("in_room", None)
                    except (ValueError, KeyError):
                        text_size = 50
                    else:
                        if in_room:
                            text_size = 45
                            status_text += f" ({in_room})"
                if self._shared.vacuum_state == "docked":
                    if int(self._shared.vacuum_battery) <= 99:
                        status_text += f" \u00B7 {charge_level}{charging} {self._shared.vacuum_battery}%"
                        self._shared.vacuum_bat_charged = False
                    else:
                        status_text += f" \u00B7 {charge_level} Ready."
                        self._shared.vacuum_bat_charged = True
                else:
                    status_text += f" \u00B7 {charge_level} {self._shared.vacuum_battery}%"
        return status_text, text_size

    async def async_draw_image_text(self, pil_img: PilPNG, color: Color) -> PilPNG:
        """Draw text on the image."""
        if pil_img is not None:
            text, size = self.get_status_text()
            if self._shared.image_ref_width > 0:
                scale_factor = pil_img.width / self._shared.image_ref_width
                size = int(size * scale_factor)
            Draw.status_text(image=pil_img, size=size, color=color, status=text)
        return pil_img

    def process_status_text(self, pil_img: PilPNG, color: Color):
        """Async function to process the image data from the Vacuum Json data."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                self.async_draw_image_text(pil_img, color)
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
                loop.run_in_executor(executor, self.process_status_text, pil_img, color)
                for pil_img in pil_img_list
            ]
            images = await gather(*tasks)

        if isinstance(images, list) and len(images) > 0:
            result = images[0]
        else:
            result = None

        return result


""" 
run_async_process_valetudo_data for MultiProcessing working mode.
It was tested and it works. It will be at the moment not used.
There is still no data coming back form the called function.


# async def run_async_process_valetudo_data(self, parsed_json):
#     num_processes = 1
#     parsed_json_list = [parsed_json for _ in range(num_processes)]
#     loop = get_event_loop()
#
#     with concurrent.futures.ProcessPoolExecutor() as executor:
#         tasks = [
#             loop.run_in_executor(executor, self.process_valetudo_data, parsed_json)
#             for parsed_json in parsed_json_list
#         ]
#         images = await gather(*tasks)
#
#     result = None
#     if isinstance(images, list) and len(images) > 0:
#         _LOGGER.debug(f"got {len(images)} elements list..")
#         result = images[0]
#
#     return result
"""

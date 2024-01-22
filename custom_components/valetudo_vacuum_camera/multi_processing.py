"""
Multiprocessing module (version 1.6.0)
This module provide the image multiprocessing in order to
avoid the overload of the main_thread of Home Assistant.
"""

from __future__ import annotations

from functools import partial
import concurrent.futures
import asyncio
import logging
import os

from .valetudo.image_handler import MapImageHandler
# from .valetudo.camera_shared import CameraShared

_LOGGER: logging.Logger = logging.getLogger(__name__)


class CameraProcessor:
    def __init__(self, camera_shared):
        self._map_handler = MapImageHandler()
        self._shared = camera_shared

    async def async_process_valetudo_data(self, parsed_json):
        if parsed_json is not None:
            pil_img = await self._map_handler.get_image_from_json(
                m_json=parsed_json,
                robot_state=self._shared.vacuum_state,
                img_rotation=self._shared.image_rotate,
                margins=self._shared.margins,
                user_colors=self._shared.get_user_colors(),
                rooms_colors=self._shared.get_rooms_colors(),
                file_name=self._shared.file_name,
                export_svg=self._shared.export_svg,
            )

            if self._shared.export_svg:
                self._shared.export_svg = False

            if pil_img is not None:
                if self._shared.map_rooms is None:
                    self._shared.map_rooms = await self._map_handler.get_rooms_attributes()
                    if self._shared.map_rooms:
                        _LOGGER.debug(f"State attributes rooms update: {self._shared.map_rooms}")

                if self._shared.show_vacuum_state:
                    status_text = f"{self._shared.file_name}: {self._shared.vacuum_state}"
                    text_size = 50
                    if self._shared.current_room:
                        try:
                            in_room = self._shared.current_room.get("in_room", None)
                        except (ValueError, KeyError):
                            text_size = 50
                        else:
                            if in_room:
                                text_size = 45
                                status_text += f", {in_room}"

                    self._map_handler.draw.status_text(
                        pil_img,
                        text_size,
                        self._shared.user_colors[8],
                        status_text,
                    )

                if self._shared.attr_calibration_points is None:
                    self._shared.attr_calibration_points = (
                        self._map_handler.get_calibration_data(self._shared.image_rotate)
                    )

                self._shared.vac_json_id = self._map_handler.get_json_id()

                if not self._shared.charger_position:
                    self._shared.charger_position = self._map_handler.get_charger_position()

                self._shared.current_room = self._map_handler.get_robot_position()

                if not self._shared.image_size:
                    self._shared.image_size = self._map_handler.get_img_size()

                if not self._shared.snapshot_taken and (
                        self._shared.vacuum_state == "idle"
                        or self._shared.vacuum_state == "docked"
                        or self._shared.vacuum_state == "error"
                ):
                    # suspend image processing if we are at the next frame.
                    if self._shared.frame_number != self._map_handler.get_frame_number():
                        self._shared.image_grab = False
                        _LOGGER.info(f"Suspended the camera data processing for: {self._shared.file_name}.")

                        # take a snapshot
                        # await ValetudoCamera.take_snapshot(parsed_json, pil_img)

            return pil_img
        return None

    def process_valetudo_data(self, parsed_json):
        # This is a non-async version of your processing function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _LOGGER.debug(f"Processing in Process ID {os.getpid()}")
        result = loop.run_until_complete(self.async_process_valetudo_data(parsed_json))
        loop.close()
        return result

    async def run_async_process_valetudo_data(self, parsed_json):
        with concurrent.futures.ProcessPoolExecutor() as executor:
            # Use partial to create a function with only one argument (parsed_json)
            # func = partial(self.process_valetudo_data, parsed_json)
            func = executor.submit(self.process_valetudo_data, parsed_json).running()
            result = await asyncio.get_event_loop().run_in_executor(executor, func)
            # result = list(executor.map(self.process_valetudo_data, parsed_json_list))
        return result

    def get_frame_number(self):
        return self._map_handler.get_frame_number() - 1

    def status_text(self, image, size, color, stat):
        return self._map_handler.draw.status_text(
            image=image,
            size=size,
            color=color,
            status=stat
        )

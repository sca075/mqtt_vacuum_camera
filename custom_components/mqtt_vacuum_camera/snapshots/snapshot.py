"""Snapshot Version 2024.08.0"""

import asyncio
from asyncio import gather, get_event_loop
import concurrent.futures
import logging
import os
import shutil

from homeassistant.helpers.storage import STORAGE_DIR

from custom_components.mqtt_vacuum_camera.const import CAMERA_STORAGE
from custom_components.mqtt_vacuum_camera.types import Any, PilPNG, SnapshotStore
from custom_components.mqtt_vacuum_camera.utils.files_operations import (
    async_populate_user_languages,
)

_LOGGER = logging.getLogger(__name__)


class Snapshots:
    """
    Snapshots class to save the JSON data and the filtered logs to a ZIP archive.
    We will use this class to save the JSON data and the filtered logs to a ZIP archive.
    """

    def __init__(self, hass, shared):
        self.hass = hass
        self._shared = shared
        self._directory_path = hass.config.path()
        self._store_all = SnapshotStore()
        self.storage_path = self.confirm_storage_path(hass)
        self.file_name = self._shared.file_name
        self.snapshot_img = f"{self.storage_path}/{self.file_name}.png"
        self._first_run = True

    @staticmethod
    def confirm_storage_path(hass) -> str:
        """Check if the storage path exists, if not create it."""
        storage_path = hass.config.path(STORAGE_DIR, CAMERA_STORAGE)
        if not os.path.exists(storage_path):
            try:
                os.makedirs(storage_path)
            except Exception as e:
                _LOGGER.warning(
                    "Snapshot Error while creating storage folder: %s", str(e)
                )
                return hass.config.path(STORAGE_DIR)
        return storage_path

    async def async_take_snapshot(self, json_data: Any, image_data: PilPNG) -> None:
        """Camera Automatic Snapshots."""
        # Save the users languages data if the Camera is the first run
        if self._first_run:
            self._first_run = False
            _LOGGER.info(f"Writing {self.file_name} users languages data.")
            await async_populate_user_languages(self.hass)
        await self._store_all.async_set_vacuum_json(self.file_name, json_data)
        try:
            # Save image ready for snapshot.
            image_data.save(self.snapshot_img)
            # Copy the image in WWW if user want it.
            if self._shared.enable_snapshots:
                if os.path.isfile(self.snapshot_img):
                    shutil.copy(
                        f"{self.storage_path}/{self.file_name}.png",
                        f"{self._directory_path}/www/snapshot_{self.file_name}.png",
                    )
                _LOGGER.debug(
                    f"\n{self.file_name}: Snapshot image saved in WWW folder."
                )
        except IOError as e:
            _LOGGER.warning(f"Error Saving {self.file_name}: Snapshot image, {str(e)}")

    def process_snapshot(self, json_data: Any, image_data: PilPNG):
        """Async function to thread the snapshot process."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                self.async_take_snapshot(json_data, image_data)
            )
        finally:
            loop.close()
        return result

    async def run_async_take_snapshot(self, json_data: Any, pil_img: PilPNG) -> None:
        """Thread function to process the image snapshots."""
        num_processes = 1
        pil_img_list = [pil_img for _ in range(num_processes)]
        loop = get_event_loop()

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=f"{self.file_name}_snapshot"
        ) as executor:
            tasks = [
                loop.run_in_executor(
                    executor,
                    self.process_snapshot,
                    json_data,
                    pil_img,
                )
                for pil_img in pil_img_list
            ]
            images = await gather(*tasks)

        if isinstance(images, list) and len(images) > 0:
            result = images[0]
        else:
            result = None

        return result

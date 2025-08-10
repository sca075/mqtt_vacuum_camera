"""Snapshot Version: 2025.3.0b0"""

import asyncio
import logging
import os
import shutil


from homeassistant.helpers.storage import STORAGE_DIR
from valetudo_map_parser.config.types import Any, PilPNG, SnapshotStore

from ..const import CAMERA_STORAGE
from ..utils.thread_pool import ThreadPoolManager
from ..utils.files_operations import async_write_json_to_disk

_LOGGER = logging.getLogger(__name__)


class Snapshots:
    """
    Snapshots class to save the JSON data and the filtered logs to a ZIP archive.
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
        self._thread_pool = ThreadPoolManager.get_instance(self.file_name)

    @staticmethod
    def confirm_storage_path(hass) -> str:
        """Check if the storage path exists, if not create it."""
        storage_path = hass.config.path(STORAGE_DIR, CAMERA_STORAGE)
        if not os.path.exists(storage_path):
            try:
                os.makedirs(storage_path)
            except OSError as e:
                _LOGGER.warning(
                    "Snapshot Error while creating storage folder: %s", str(e)
                )
                return hass.config.path(STORAGE_DIR)
        return storage_path

    async def process_snapshot(self, json_data: Any, image_data: PilPNG) -> None:
        """Process the snapshot synchronously.

        This function is called from the thread pool.
        Stores both the JSON data and the image.
        """
        try:
            # Store JSON data if provided
            if json_data and not isinstance(json_data, bool):
                # Use synchronous file operations since we're in a thread
                json_file_path = os.path.join(
                    self.storage_path, f"{self.file_name}.json"
                )
                await async_write_json_to_disk(json_file_path, json_data)
                _LOGGER.debug("%s: JSON data saved to storage", self.file_name)

            # Save image ready for snapshot
            image_data.save(self.snapshot_img)

            # Copy the image to WWW if enabled
            if self._shared.enable_snapshots and os.path.isfile(self.snapshot_img):
                await asyncio.to_thread(shutil.copy,
                    os.path.join(self.storage_path, f"{self.file_name}.png"),
                    os.path.join(
                        self._directory_path, "www", f"snapshot_{self.file_name}.png"
                    ),
                )
                _LOGGER.debug("%s: Snapshot image saved in WWW folder.", self.file_name)

            # Ensure image is closed to prevent resource leaks
            if hasattr(image_data, "close"):
                image_data.close()

            return None
        except (IOError, OSError) as e:
            _LOGGER.error("Error in process_snapshot: %s", str(e))
            # Ensure image is closed even on error
            if hasattr(image_data, "close"):
                image_data.close()
            return None

    async def run_async_take_snapshot(self, json_data: Any, pil_img: PilPNG) -> None:
        """Process the image snapshot using the thread pool manager."""

        return await self._thread_pool.run_async_in_executor(
            "camera_snapshot", self.process_snapshot, json_data, pil_img
        )


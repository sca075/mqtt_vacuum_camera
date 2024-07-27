"""Snapshot Version 2024.08.0"""

import asyncio
from asyncio import gather, get_event_loop
import concurrent.futures
import logging
import os
import shutil
import zipfile

from homeassistant.helpers.storage import STORAGE_DIR

from custom_components.mqtt_vacuum_camera.const import CAMERA_STORAGE, DOMAIN
from custom_components.mqtt_vacuum_camera.types import (
    Any,
    JsonType,
    PilPNG,
    SnapshotStore,
)
from custom_components.mqtt_vacuum_camera.utils.files_operations import (
    async_populate_user_languages,
    async_write_file_to_disk,
    async_write_json_to_disk,
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

    async def async_get_filtered_logs(self):
        """Make a copy of home-assistant.log to home-assistant.tmp"""
        log_file_path = os.path.join(self._directory_path, "home-assistant.log")
        tmp_log_file_path = os.path.join(self._directory_path, f"{self.file_name}.tmp")

        try:
            if os.path.exists(log_file_path):
                shutil.copyfile(log_file_path, tmp_log_file_path)

            filtered_logs = []

            if os.path.exists(tmp_log_file_path):
                with open(tmp_log_file_path) as log_file:
                    for line in log_file:
                        if f"custom_components.{DOMAIN}" in line:
                            filtered_logs.append(line.strip())

                # Delete the temporary log file
                os.remove(tmp_log_file_path)

            return "\n".join(filtered_logs)

        except FileNotFoundError as e:
            _LOGGER.warning("Snapshot Error while processing logs: %s", str(e))
            return ""

    async def async_get_data(self, file_name: str, json_data: JsonType) -> Any:
        """Get the data to compose the snapshot logs."""
        try:
            # Save JSON data to a file
            if json_data:
                json_file_name = os.path.join(self.storage_path, f"{file_name}.json")
                await async_write_json_to_disk(json_file_name, json_data)

            # Save log data to a file
            log_data = await self.async_get_filtered_logs()
            if log_data:
                log_file_name = os.path.join(self.storage_path, f"{file_name}.log")
                await async_write_file_to_disk(log_file_name, log_data)

        except Exception as e:
            _LOGGER.warning("Snapshot Error while saving data: %s", str(e))

    def zip_snapshot(self, file_name: str) -> Any:
        """Create a ZIP archive"""
        zip_file_name = os.path.join(self.storage_path, f"{file_name}.zip")

        try:
            with zipfile.ZipFile(zip_file_name, "w", zipfile.ZIP_DEFLATED) as zf:
                json_file_name = os.path.join(self.storage_path, f"{file_name}.json")
                log_file_name = os.path.join(self.storage_path, f"{file_name}.log")
                png_file_name = os.path.join(self.storage_path, f"{file_name}.png")
                raw_file_name = os.path.join(self.storage_path, f"{file_name}.raw")

                # Add the Vacuum JSON file to the ZIP archive
                if os.path.exists(json_file_name):
                    _LOGGER.debug("Adding %s to the ZIP archive", json_file_name)
                    zf.write(json_file_name, os.path.basename(json_file_name))
                    os.remove(json_file_name)

                # Add the HA filtered log file to the ZIP archive
                if os.path.exists(log_file_name):
                    _LOGGER.debug("Adding %s to the ZIP archive", log_file_name)
                    zf.write(log_file_name, os.path.basename(log_file_name))
                    os.remove(log_file_name)

                # Add the PNG file to the ZIP archive
                if os.path.exists(png_file_name):
                    _LOGGER.debug("Adding %s to the ZIP archive", png_file_name)
                    zf.write(png_file_name, os.path.basename(png_file_name))

                # Check if the MQTT file_name.raw exists
                if os.path.exists(raw_file_name):
                    _LOGGER.debug("Adding %s to the ZIP archive", raw_file_name)
                    # Add the .raw file to the ZIP archive
                    zf.write(raw_file_name, os.path.basename(raw_file_name))
                    # Remove the .raw file
                    os.remove(raw_file_name)

        except Exception as e:
            _LOGGER.warning("Error while creating logs ZIP archive: %s", str(e))

    async def async_data_snapshot(self, file_name: str, json_data: any) -> None:
        """
        Save Vacuum JSON data and filtered logs to a ZIP archive.
        :param file_name: Vacuum friendly name
        :param json_data: Vacuum JSON data
        """
        try:
            # When logger is active.
            if (_LOGGER.getEffectiveLevel() > 0) and (
                _LOGGER.getEffectiveLevel() != 30
            ):
                await self.async_get_data(file_name, json_data)
                self.zip_snapshot(file_name)
        except Exception as e:
            _LOGGER.warning("Error while creating logs snapshot: %s", str(e))

    async def async_take_snapshot(self, json_data: Any, image_data: PilPNG) -> None:
        """Camera Automatic Snapshots."""
        # Save the users languages data if the Camera is the first run
        if self._first_run:
            self._first_run = False
            _LOGGER.info(f"Writing {self.file_name} users languages data.")
            await async_populate_user_languages(self.hass)
        await self._store_all.async_set_vacuum_json(self.file_name, json_data)
        if await self._store_all.async_get_snapshot_save_data(self.file_name):

            try:
                await self.async_data_snapshot(self.file_name, json_data)
            except IOError as e:
                _LOGGER.warning(
                    f"Error Saving {self.file_name}: Snapshot data, {str(e)}"
                )
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

"""Snapshot Version 2024.06.0"""

import asyncio
from asyncio import gather, get_event_loop
import concurrent.futures
import json
import logging
import os
import shutil
import zipfile

from homeassistant.helpers.storage import STORAGE_DIR

from custom_components.valetudo_vacuum_camera.types import Any, JsonType, PilPNG
from custom_components.valetudo_vacuum_camera.utils.users_data import (
    async_write_languages_json,
)

_LOGGER = logging.getLogger(__name__)  # Create a logger instance


class Snapshots:
    """
    Snapshots class to save the JSON data and the filtered logs to a ZIP archive.
    We will use this class to save the JSON data and the filtered logs to a ZIP archive.
    """

    def __init__(self, hass, mqtt, shared):
        self._mqtt = mqtt
        self.hass = hass
        self._shared = shared
        self._directory_path = hass.config.path()
        self.storage_path = f"{hass.config.path(STORAGE_DIR)}/valetudo_camera"
        if not os.path.exists(self.storage_path):
            self._storage_path = f"{self._directory_path}/{STORAGE_DIR}"
        self.file_name = self._shared.file_name
        self.snapshot_img = f"{self.storage_path}/{self.file_name}.png"
        self._first_run = True

    async def async_get_room_data(self) -> None:
        """Get the Vacuum Rooms data and save it to a file."""
        vacuum_id = self.file_name
        # New file room_data to be saved / updated
        data_file_path = os.path.join(self.storage_path, f"room_data_{vacuum_id}.json")
        un_formated_room_data = self._shared.map_rooms
        _LOGGER.debug(f"Rooms data of {vacuum_id}: {un_formated_room_data}")
        if not un_formated_room_data:
            _LOGGER.debug(f"No rooms data found for {vacuum_id} to save.")
            return
        room_data = {
            "segments": len(un_formated_room_data),
            "rooms": {}
        }
        for room_id, room_info in un_formated_room_data.items():
            room_data["rooms"][room_id] = {
                "number": room_info["number"],
                "name": room_info["name"],
            }
        if room_data:
            try:
                with open(data_file_path, "w") as language_file:
                    json.dump(room_data, language_file, indent=2)
                _LOGGER.info(f"\nRooms data of {vacuum_id} saved to {data_file_path}")
            except Exception as e:
                _LOGGER.warning(f"Failed to save rooms data of {vacuum_id}: {e}")

    async def async_get_filtered_logs(self):
        """Make a copy of home-assistant.log to home-assistant.tmp"""
        log_file_path = os.path.join(self._directory_path, "home-assistant.log")
        tmp_log_file_path = os.path.join(self._directory_path, "home-assistant.tmp")

        try:
            if os.path.exists(log_file_path):
                shutil.copyfile(log_file_path, tmp_log_file_path)

            filtered_logs = []

            if os.path.exists(tmp_log_file_path):
                with open(tmp_log_file_path) as log_file:
                    for line in log_file:
                        if "custom_components.valetudo_vacuum_camera" in line:
                            filtered_logs.append(line.strip())

                # Delete the temporary log file
                os.remove(tmp_log_file_path)

            return "\n".join(filtered_logs)

        except FileNotFoundError as e:
            _LOGGER.warning("Snapshot Error while processing logs: %s", str(e))
            return ""

    async def async_get_data(self, file_name: str, json_data: JsonType) -> None:
        """Get the data to compose the snapshot logs."""
        # Create the storage folder if it doesn't exist
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path)

        try:
            # Save JSON data to a file
            json_file_name = os.path.join(self.storage_path, f"{file_name}.json")
            with open(json_file_name, "w") as json_file:
                json.dump(json_data, json_file, indent=4)

            log_data = await self.async_get_filtered_logs()

            # Save log data to a file
            log_file_name = os.path.join(self.storage_path, f"{file_name}.log")
            with open(log_file_name, "w") as log_file:
                log_file.write(log_data)
            if self._first_run:
                self._first_run = False
                _LOGGER.info("Getting the users languages data.")
                await async_write_languages_json(self.hass)
                _LOGGER.info("Getting vacuum rooms data.")
                await self.async_get_room_data()

        except Exception as e:
            _LOGGER.warning("Snapshot Error while saving data: %s", str(e))

    def _zip_snapshot(self, file_name: str) -> None:
        """Create a ZIP archive"""
        zip_file_name = os.path.join(self.storage_path, f"{file_name}.zip")

        try:
            with zipfile.ZipFile(zip_file_name, "w", zipfile.ZIP_DEFLATED) as zf:
                json_file_name = os.path.join(self.storage_path, f"{file_name}.json")
                log_file_name = os.path.join(self.storage_path, f"{file_name}.log")
                png_file_name = os.path.join(self.storage_path, f"{file_name}.png")

                # Add the JSON file to the ZIP archive
                zf.write(json_file_name, os.path.basename(json_file_name))

                # Add the log file to the ZIP archive
                zf.write(log_file_name, os.path.basename(log_file_name))

                # Add the PNG file to the ZIP archive
                zf.write(png_file_name, os.path.basename(png_file_name))

                # Check if the file_name.raw exists
                raw_file_name = os.path.join(self.storage_path, f"{file_name}.raw")
                if os.path.exists(raw_file_name):
                    # Add the .raw file to the ZIP archive
                    zf.write(raw_file_name, os.path.basename(raw_file_name))
                    # Remove the .raw file
                    os.remove(raw_file_name)

        except Exception as e:
            _LOGGER.warning("Error while creating logs ZIP archive: %s", str(e))

        # Clean up the original files
        try:
            os.remove(json_file_name)
            os.remove(log_file_name)
        except Exception as e:
            _LOGGER.warning("Error while cleaning up original files: %s", str(e))

    async def async_data_snapshot(self, file_name: str, json_data: any) -> None:
        """
        Save JSON data and filtered logs to a ZIP archive.
        :param file_name: Vacuum friendly name
        :param json_data: Vacuum JSON data
        """
        try:
            await self.async_get_data(file_name, json_data)
            self._zip_snapshot(file_name)
        except Exception as e:
            _LOGGER.warning("Error while creating logs snapshot: %s", str(e))

    async def async_take_snapshot(self, json_data: Any, image_data: PilPNG) -> None:
        """Camera Automatic Snapshots."""
        try:
            # When logger is active.
            if (_LOGGER.getEffectiveLevel() > 0) and (
                _LOGGER.getEffectiveLevel() != 30
            ):
                # Save mqtt raw data file.
                if self._mqtt is not None:
                    await self._mqtt.save_payload(self.file_name)
                # Write the JSON and data to the file.
                await self.async_data_snapshot(self.file_name, json_data)
            # Save image ready for snapshot.
            image_data.save(self.snapshot_img)  # Save the image in .storage
            if self._shared.enable_snapshots:
                if os.path.isfile(self.snapshot_img):
                    shutil.copy(
                        f"{self.storage_path}/{self.file_name}.png",
                        f"{self._directory_path}/www/snapshot_{self.file_name}.png",
                    )
        except IOError:
            self._shared.snapshot_take = None
            _LOGGER.warning(
                f"Error Saving {self.file_name}: Snapshot, will not be available till restart."
            )
        else:
            _LOGGER.debug(
                f"\n{self.file_name}: Snapshot acquire and saved on WWW during "
                f"{self._shared.vacuum_state} Vacuum State."
            )

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

"""Debug logs collection for MQTT Vacuum Camera.
Version: 2025.10.0"""

import asyncio
from asyncio import gather, get_event_loop
import concurrent.futures
import logging
import os
import shutil
from typing import Any
import zipfile

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR

from ..const import CAMERA_STORAGE, DOMAIN
from ..utils.files_operations import async_write_file_to_disk

_LOGGER = logging.getLogger(__name__)


async def async_get_filtered_logs(base_path, directory_path: str, file_name):
    """Make a copy of home-assistant.log to home-assistant.tmp"""
    log_file_path = os.path.join(base_path, "home-assistant.log")
    tmp_log_file_path = os.path.join(directory_path, f"{file_name}.tmp")

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


def zip_logs(storage_dir: str, file_name: str) -> Any:
    """Create a ZIP archive with filtered logs and raw MQTT data."""
    zip_file_name = os.path.join(storage_dir, f"{file_name}.zip")

    try:
        with zipfile.ZipFile(zip_file_name, "w", zipfile.ZIP_DEFLATED) as zf:
            log_file_name = os.path.join(storage_dir, f"{file_name}.log")
            raw_file_name = os.path.join(storage_dir, f"{file_name}.raw")

            # Add the HA filtered log file to the ZIP archive
            if os.path.exists(log_file_name):
                _LOGGER.debug("Adding %s to the ZIP archive", log_file_name)
                zf.write(log_file_name, os.path.basename(log_file_name))
                os.remove(log_file_name)

            # Check if the MQTT raw data exists
            if os.path.exists(raw_file_name):
                _LOGGER.debug("Adding %s to the ZIP archive", raw_file_name)
                zf.write(raw_file_name, os.path.basename(raw_file_name))
                os.remove(raw_file_name)

    except Exception as e:
        _LOGGER.warning("Error while creating logs ZIP archive: %s", str(e))


async def async_get_data(base_path: str, storage_path: str, file_name: str) -> Any:
    """Get the filtered logs data for debug ZIP."""
    try:
        # Save log data to a file
        log_data = await async_get_filtered_logs(base_path, storage_path, file_name)
        if log_data:
            log_file_name = os.path.join(storage_path, f"{file_name}.log")
            await async_write_file_to_disk(log_file_name, log_data)

    except Exception as e:
        _LOGGER.warning("Error while saving log data: %s", str(e))


async def async_logs_store(hass: HomeAssistant, file_name: str) -> None:
    """Save filtered logs and raw MQTT data to a ZIP archive for debugging."""
    storage_path = confirm_storage_path(hass)
    base_path = hass.config.path()
    try:
        # When logger is active (not at WARNING level 30)
        if (_LOGGER.getEffectiveLevel() > 0) and (_LOGGER.getEffectiveLevel() != 30):
            await async_get_data(base_path, storage_path, file_name)
            zip_logs(storage_path, file_name)
            if os.path.exists(f"{storage_path}/{file_name}.zip"):
                source_path = f"{storage_path}/{file_name}.zip"
                destination_path = f"{hass.config.path()}/www/{file_name}.zip"
                shutil.copy(source_path, destination_path)
    except Exception as e:
        _LOGGER.warning("Error while creating debug logs ZIP: %s", str(e))


def confirm_storage_path(hass) -> str:
    """Check if the storage path exists, if not create it."""
    storage_path = hass.config.path(STORAGE_DIR, CAMERA_STORAGE)
    if not os.path.exists(storage_path):
        try:
            os.makedirs(storage_path)
        except Exception as e:
            _LOGGER.warning("Snapshot Error while creating storage folder: %s", str(e))
            return hass.config.path(STORAGE_DIR)
    return storage_path


def process_logs(hass: HomeAssistant, file_name: str):
    """Process logs for snapshot.

    This is a synchronous wrapper around the async logs storage function,
    designed to be called from a thread pool.
    """
    # Use asyncio.run which properly manages the event loop lifecycle
    try:
        return asyncio.run(async_logs_store(hass, file_name))
    except Exception as e:
        _LOGGER.error("Error in process_logs: %s", str(e), exc_info=True)
        return None


async def run_async_save_logs(hass: HomeAssistant, file_name: str) -> None:
    """Thread function to process the image snapshots."""
    loop = get_event_loop()

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=1, thread_name_prefix=f"{file_name}_LogsSave"
    ) as executor:
        tasks = [
            loop.run_in_executor(
                executor,
                process_logs,
                hass,
                file_name,
            )
        ]
        logs_save = await gather(*tasks)

    result = (
        logs_save[0] if isinstance(logs_save, list) and len(logs_save) > 0 else None
    )

    return result

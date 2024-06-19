"""
Migration script to update the domain and platform.
Config entries and entity registry entries in Home Assistant.
Transfer the data of Valetudo Vacuum Camera to MQTT Vacuum Camera.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import logging
import os
import shutil
from typing import Any
import zipfile

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR

_LOGGER = logging.getLogger(__name__)


async def async_load_file(file_to_load: str, is_json: bool = False) -> Any:
    """Asynchronously load JSON data from a file."""
    loop = asyncio.get_event_loop()

    def read_file(my_file: str, read_json: bool = False):
        """Helper function to read data from a file."""
        try:
            if read_json:
                with open(my_file) as file:
                    return json.load(file)
            else:
                with open(my_file) as file:
                    return file.read()
        except (FileNotFoundError, json.JSONDecodeError):
            _LOGGER.warning(f"{my_file} does not exist.")
            return None

    try:
        return await loop.run_in_executor(None, read_file, file_to_load, is_json)
    except FileNotFoundError as e:
        _LOGGER.warning(f"Blocking IO issue detected: {e}")
    except json.JSONDecodeError as e:
        _LOGGER.warning(f"Error reading JSON file: {e}")
        return None


def make_dir(directory: str) -> bool:
    """Asynchronously create a directory."""
    try:
        os.mkdir(directory)
    except OSError as e:
        _LOGGER.error(f"Error creating output directory: {str(e)}")
        return False
    return True


async def async_write_json_to_disk(file_to_write: str, json_data) -> None:
    """Asynchronously write data to a JSON file."""
    loop = asyncio.get_event_loop()

    def _write_to_file(file_path, data):
        """Helper function to write data to a file."""
        with open(file_path, "w") as datafile:
            json.dump(data, datafile, indent=2)

    try:
        await loop.run_in_executor(None, _write_to_file, file_to_write, json_data)
    except Exception as e:
        _LOGGER.warning(f"Blocking issue detected: {e}")


async def async_write_file_to_disk(
    file_to_write: str, data, is_binary: bool = False
) -> None:
    """Asynchronously write data to a file."""
    loop = asyncio.get_event_loop()

    def _write_to_file(file_path, data_to_write, binary_mode):
        """Helper function to write data to a file."""
        if binary_mode:
            with open(file_path, "wb") as datafile:
                datafile.write(data_to_write)
        else:
            with open(file_path, "w") as datafile:
                datafile.write(data_to_write)

    try:
        await loop.run_in_executor(None, _write_to_file, file_to_write, data, is_binary)
    except Exception as e:
        _LOGGER.warning(f"Blocking issue detected: {e}")


def unzip_file(file_path: str, output_dir: str):
    """Unzip a file to the specified directory."""
    make_dir(output_dir)

    done = False  # Initialize done as False
    if zipfile.is_zipfile(file_path):
        _LOGGER.info(f"Unzipping {file_path} to {output_dir}")
        try:
            with zipfile.CompleteDirs(file_path) as zip_ref:
                zip_ref.extractall(output_dir)
            done = True  # Set done to True only if extraction succeeds
        except zipfile.BadZipFile:
            _LOGGER.error(f"Corrupted zip file: {file_path}")
        except Exception as e:
            _LOGGER.error(f"Failed to unzip file {file_path}: {str(e)}")
    else:
        _LOGGER.error(f"Invalid zip file: {file_path}")

    if done:
        # Additional checks can be added here to ensure all expected files are present
        _LOGGER.info("Unzip operation completed successfully, proceeding to cleanup.")
        folder_to_delete = os.path.join(
            os.getcwd(), "custom_components", "valetudo_vacuum_camera"
        )
        delete_old_folder(folder_to_delete)
    else:
        _LOGGER.error("Unzip operation failed, old folder will not be deleted.")


async def async_unzip(zip_path, extract_to):
    """
    Run the unzip operation in a separate thread.
    """
    with ThreadPoolExecutor(max_workers=2) as executor:
        future = executor.submit(unzip_file, zip_path, extract_to)
        return future.result()


async def async_copy_file(src: str, dst: str) -> bool:
    """Copy a file from src to dst."""
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, lambda: shutil.copy2(src, dst))
        _LOGGER.info(f"File copied from {src} to {dst}")
    except Exception as e:
        _LOGGER.error(f"Error copying file: {str(e)}")
        return False
    return True


async def async_update_entry_field(entry, key, old_str, new_str):
    """Recursively update values if they contain the old_str."""
    if isinstance(entry, dict):
        for k, v in entry.items():
            if isinstance(v, (dict, list)):
                await async_update_entry_field(v, k, old_str, new_str)
            elif isinstance(v, str) and old_str in v:
                entry[k] = v.replace(old_str, new_str)
                _LOGGER.info(f"Updated {k} from {old_str} to {new_str}")
    elif isinstance(entry, list):
        for item in entry:
            await async_update_entry_field(item, key, old_str, new_str)


async def async_migrate_config_entries(
    file_path: str, old_domain: str, new_domain: str
):
    """Migrate the domain and platform in the config entries file."""
    # Check if the file exists
    if not os.path.exists(file_path):
        _LOGGER.error(f"File not found: {file_path}")
        return False

    # Load the JSON data from the file
    try:
        data = await async_load_file(file_path, is_json=True)
    except json.JSONDecodeError as e:
        _LOGGER.error(f"Error reading JSON file: {str(e)}")
        return False

    # Modify the entries
    modified = False
    try:
        for entry in data["data"]["entries"]:
            # Update domain in the entry
            if entry["domain"] == old_domain:
                entry["domain"] = new_domain
                _LOGGER.info(f"Domain updated for entry_id {entry['entry_id']}")

            # Update platform and other nested keys
            await async_update_entry_field(entry, None, old_domain, new_domain)

            modified = True

        # Save the changes back to the file if modifications have been made
        if modified:
            try:
                await async_write_json_to_disk(file_path, data)
                _LOGGER.info("Successfully updated the config_entries file.")
            except Exception as e:
                _LOGGER.error(f"Error writing JSON file: {str(e)}")
                return "Error writing JSON file"

        else:
            _LOGGER.info("No modifications needed.")
    except Exception as e:
        _LOGGER.error(f"Error updating config entries: {str(e)}")
        return False

    return True


async def async_migrate_entity_registry(file_path, old_platform, new_platform):
    """Migrate the platform in the entity registry file."""
    # Check if the file exists
    if not os.path.exists(file_path):
        _LOGGER.error(f"File not found: {file_path}")
        return "File not found"

    # Load the JSON data from the file
    try:
        data = await async_load_file(file_path, is_json=True)
    except json.JSONDecodeError as e:
        _LOGGER.error(f"Error reading JSON file: {str(e)}")
        return "Error reading JSON file"

    # Modify the entries
    try:
        modified = False
        for entity in data["data"]["entities"]:
            if entity.get("platform", "") == old_platform:
                original_platform = entity["platform"]
                entity["platform"] = new_platform
                _LOGGER.info(
                    f"Updated platform from {original_platform} to {entity['platform']} "
                    f"for entity_id {entity['entity_id']}"
                )
                modified = True

        # Save the changes back to the file if modifications have been made
        if modified:
            try:
                await async_write_json_to_disk(file_path, data)
                _LOGGER.info("Successfully updated the entity_registry file.")
            except Exception as e:
                _LOGGER.error(f"Error writing JSON file: {str(e)}")
                return "Error writing JSON file"
        else:
            _LOGGER.info("No modifications were needed.")
    except Exception as e:
        _LOGGER.error(f"Error updating entity registry: {str(e)}")
        return False

    return True


def delete_old_folder(path):
    """Delete the old folder."""
    try:
        shutil.rmtree(path)
        _LOGGER.info(f"Successfully deleted the folder at {path}")
    except FileNotFoundError:
        _LOGGER.warning(f"No folder found at {path} to delete.")
    except Exception as e:
        _LOGGER.warning(f"Failed to delete the folder at {path}: {str(e)}")


async def async_migrate_entries(hass: HomeAssistant) -> bool:
    """Migrate Valetudo Vacuum Camera to MQTT Vacuum Camera."""
    # Define the file to edit
    file1 = "core.config_entries"
    file2 = "core.entity_registry"
    # Define the paths
    base_path = hass.config.path()  # os.getcwd()
    camera_storage_path = hass.config.path(STORAGE_DIR, "valetudo_camera")
    if not os.path.exists(camera_storage_path):
        make_dir(camera_storage_path)
    file1_path = hass.config.path(STORAGE_DIR, file1)
    file2_path = hass.config.path(STORAGE_DIR, file2)
    if os.path.exists(file1_path) and os.path.exists(file2_path):
        await async_copy_file(file1_path, os.path.join(camera_storage_path, file1))
        await async_copy_file(file2_path, os.path.join(camera_storage_path, file2))
    else:
        _LOGGER.error(f"File not found: {file1_path}")
        return False
    # Define the work directory
    worker_dir = hass.config.path(
        "custom_components", "valetudo_vacuum_camera", "tmp_migrate"
    )
    zip_file = os.path.join(worker_dir, "mqtt_vacuum_camera.zip")  # Zip file to extract
    unzip_dir = os.path.join(base_path, "custom_components", "mqtt_vacuum_camera")
    # Unzip the files to the work directory
    await async_unzip(zip_file, unzip_dir)
    # Migrate the config entries and entity registry
    await async_migrate_config_entries(
        os.path.join(camera_storage_path, file1),
        "valetudo_vacuum_camera",
        "mqtt_vacuum_camera",
    )
    await async_migrate_entity_registry(
        os.path.join(camera_storage_path, file2),
        "valetudo_vacuum_camera",
        "mqtt_vacuum_camera",
    )
    # Copy the files back to the storage directory
    await async_copy_file(os.path.join(camera_storage_path, file1), file1_path)
    await async_copy_file(os.path.join(camera_storage_path, file2), file2_path)
    return True

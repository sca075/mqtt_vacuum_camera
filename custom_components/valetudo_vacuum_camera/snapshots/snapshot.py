"""Snapshot Version 1.4.3"""
# Added Errors handling.

import os
import json
import zipfile
import shutil
import logging

_LOGGER = logging.getLogger(__name__)  # Create a logger instance

class Snapshots:
    def __init__(self, storage_path):
        self.storage_path = storage_path

    @staticmethod
    def _get_filtered_logs():
        # Make a copy of home-assistant.log to home-assistant.tmp
        log_file_path = os.path.join(os.getcwd(), "home-assistant.log")
        tmp_log_file_path = os.path.join(os.getcwd(), "home-assistant.tmp")

        try:
            if os.path.exists(log_file_path):
                shutil.copyfile(log_file_path, tmp_log_file_path)

            filtered_logs = []

            if os.path.exists(tmp_log_file_path):
                with open(tmp_log_file_path, "r") as log_file:
                    for line in log_file:
                        if "custom_components.valetudo_vacuum_camera" in line:
                            filtered_logs.append(line.strip())

                # Delete the temporary log file
                os.remove(tmp_log_file_path)

            return "\n".join(filtered_logs)

        except Exception as e:
            _LOGGER.warning("Error while processing logs: %s", str(e))
            return ""

    def _get_data(self, file_name, json_data):
        # Create the storage folder if it doesn't exist
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path)

        try:
            # Save JSON data to a file
            json_file_name = os.path.join(self.storage_path, file_name + ".json")
            with open(json_file_name, "w") as json_file:
                json.dump(json_data, json_file, indent=4)

            log_data = self._get_filtered_logs()

            # Save log data to a file
            log_file_name = os.path.join(self.storage_path, file_name + ".log")
            with open(log_file_name, "w") as log_file:
                log_file.write(log_data)

        except Exception as e:
            _LOGGER.warning("Error while saving data: %s", str(e))

    def _zip_snapshot(self, file_name):
        # Create a ZIP archive
        zip_file_name = os.path.join(self.storage_path, file_name + ".zip")

        try:
            with zipfile.ZipFile(zip_file_name, "w", zipfile.ZIP_DEFLATED) as zf:
                json_file_name = os.path.join(self.storage_path, file_name + ".json")
                log_file_name = os.path.join(self.storage_path, file_name + ".log")

                # Add the JSON file to the ZIP archive
                zf.write(json_file_name, os.path.basename(json_file_name))

                # Add the log file to the ZIP archive
                zf.write(log_file_name, os.path.basename(log_file_name))

                # Check if the file_name.raw exists
                raw_file_name = os.path.join(self.storage_path, file_name + ".raw")
                if os.path.exists(raw_file_name):
                    # Add the .raw file to the ZIP archive
                    zf.write(raw_file_name, os.path.basename(raw_file_name))
                    # Remove the .raw file
                    os.remove(raw_file_name)

        except Exception as e:
            _LOGGER.warning("Error while creating ZIP archive: %s", str(e))

        # Clean up the original files
        try:
            os.remove(json_file_name)
            os.remove(log_file_name)
        except Exception as e:
            _LOGGER.warning("Error while cleaning up original files: %s", str(e))

    def data_snapshot(self, file_name, json_data):
        try:
            self._get_data(file_name, json_data)
            self._zip_snapshot(file_name)
        except Exception as e:
            _LOGGER.warning("Error while creating snapshot: %s", str(e))

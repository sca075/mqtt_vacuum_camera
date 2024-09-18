"""MQTT Vacuum Camera Coordinator."""

from datetime import timedelta
import logging
from typing import Optional

import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .camera_shared import CameraShared, CameraSharedManager
from .common import get_camera_device_info
from .const import DEFAULT_NAME
from .valetudo.MQTT.connector import ValetudoConnector

_LOGGER = logging.getLogger(__name__)


class MQTTVacuumCoordinator(DataUpdateCoordinator):
    """Coordinator for MQTT Vacuum Camera."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        vacuum_topic: str,
        polling_interval=timedelta(seconds=3),
    ):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DEFAULT_NAME,
            update_interval=polling_interval,
        )
        self.hass: HomeAssistant = hass
        self.vacuum_topic: str = vacuum_topic
        self.device_entity: ConfigEntry = entry
        self.device_info: DeviceInfo = get_camera_device_info(hass, self.device_entity)
        self.shared_manager: Optional[CameraSharedManager] = None
        self.shared: Optional[CameraShared] = None
        self.file_name: str = ""
        self.connector: Optional[ValetudoConnector] = None
        self.in_sync_with_camera: bool = False

        # Initialize shared data and MQTT connector
        self.shared, self.file_name = self._init_shared_data(self.vacuum_topic)
        self.stat_up_mqtt()

    def _init_shared_data(self, mqtt_listen_topic: str) -> tuple[CameraShared, str]:
        """
        Initialize the shared data.

        Args:
            mqtt_listen_topic (str): The topic to listen for MQTT messages.

        Returns:
            tuple[CameraShared, str]: The CameraShared instance and file name.
        """
        shared = None
        file_name = None

        if mqtt_listen_topic and not self.shared_manager:
            file_name = mqtt_listen_topic.split("/")[1].lower()
            self.shared_manager = CameraSharedManager(file_name, self.device_info)
            shared = self.shared_manager.get_instance()
            _LOGGER.debug(f"Camera {file_name} Starting up..")

        return shared, file_name

    def stat_up_mqtt(self) -> ValetudoConnector:
        """
        Initialize the MQTT Connector.

        Returns:
            ValetudoConnector: The initialized MQTT connector.
        """
        self.connector = ValetudoConnector(self.vacuum_topic, self.hass, self.shared)
        return self.connector

    def update_shared_data(self, dev_info: DeviceInfo) -> tuple[CameraShared, str]:
        """
        Create or update the instance of the shared data.

        Args:
            dev_info (DeviceInfo): The device information to update.

        Returns:
            tuple[CameraShared, str]: Updated shared data and file name.
        """
        self.shared_manager.update_shared_data(dev_info)
        self.shared = self.shared_manager.get_instance()
        self.in_sync_with_camera = True
        return self.shared, self.file_name

    async def _async_update_data(self, process: bool = True):
        """
        Fetch data from the MQTT topics.

        Args:
            process (bool): Whether to process the data (default: True).

        Returns:
            The fetched data from MQTT.
        """
        try:
            async with async_timeout.timeout(10):
                # Fetch and process maps data from the MQTT connector
                return await self.connector.update_data(process)
        except ConfigEntryAuthFailed as err:
            raise ConfigEntryAuthFailed from err
        except Exception as err:
            _LOGGER.error(f"Error communicating with MQTT or processing data: {err}")
            raise UpdateFailed(f"Error communicating with MQTT: {err}") from err

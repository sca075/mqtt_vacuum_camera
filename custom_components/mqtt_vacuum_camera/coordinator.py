"""MQTT Vacuum Camera Coordinator."""

from datetime import timedelta
import logging

import async_timeout
from homeassistant.exceptions import ConfigEntryAuthFailed

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .camera_shared import CameraSharedManager
from .const import DEFAULT_NAME
from .common import get_camera_device_info
from .valetudo.MQTT.connector import ValetudoConnector
# from .snapshots.snapshot import Snapshots
# from .camera_processing import CameraProcessor

_LOGGER = logging.getLogger(__name__)


class MQTTVacuumCoordinator(DataUpdateCoordinator):
    """Coordinator for MQTT Vacuum Camera."""

    def __init__(
        self,
        hass,
        entry,
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
        self.hass = hass
        self.vacuum_topic = vacuum_topic
        self.device_entity = entry
        self.device_info = get_camera_device_info(hass, self.device_entity)
        self.shared_manager = None
        self.shared, self.file_name = self._init_shared_data(self.vacuum_topic)
        self.connector = None
        # self.snapshot = Snapshots(hass, self.shared)
        # self.camera_processor = CameraProcessor(hass, self.shared)
        self.stat_up_mqtt()



    def _init_shared_data(self, mqtt_listen_topic: str):
        """Initialize the shared data."""
        shared, file_name = None, None
        if mqtt_listen_topic and not self.shared_manager:
            file_name = mqtt_listen_topic.split("/")[1].lower()
            self.shared_manager = CameraSharedManager(file_name, self.device_info)
            shared = self.shared_manager.get_instance()
            _LOGGER.debug(f"Camera {file_name} Starting up..")
        return shared, file_name

    async def _async_setup(self):
        """Set up the coordinator."""
        self._device = self.device_info
        _LOGGER.info(f"Setting up coordinator for {self.file_name}.")

    def stat_up_mqtt(self):
        """Init the MQTT Connector"""
        self.connector = ValetudoConnector(self.vacuum_topic, self.hass, self.shared)
        return self.connector

    def update_shared_data(self, dev_info):
        """Create / update instance of the shared data"""
        self.shared_manager.update_shared_data(dev_info)
        self.shared = self.shared_manager.get_instance()
        return self.shared, self.file_name

    async def _async_update_data(self, process: bool = True):
        """Fetch data from the MQTT topics."""
        try:
            # conside adding shared updates here ***
            async with async_timeout.timeout(10):
                # Fetch and process data from the MQTT connector
                return await self.connector.update_data(process)
        except ConfigEntryAuthFailed as err:
            raise ConfigEntryAuthFailed from err
        except Exception as err:
            _LOGGER.error(f"Error communicating with MQTT or processing data: {err}")
            raise UpdateFailed(f"Error communicating with MQTT: {err}") from err

    async def async_will_remove_from_hass(self):
        """Handle cleanup when the coordinator is removed."""
        _LOGGER.info(f"Cleaning up {self.file_name} coordinator.")
        await self.connector.async_unsubscribe_from_topics()

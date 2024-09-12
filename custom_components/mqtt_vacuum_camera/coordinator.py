"""MQTT Vacuum Camera Coordinator."""

from datetime import timedelta
import logging

import async_timeout
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed

# from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .camera_shared import CameraSharedManager
from .const import DEFAULT_NAME
from .valetudo.MQTT.connector import ValetudoConnector

_LOGGER = logging.getLogger(__name__)


class MQTTVacuumCoordinator(DataUpdateCoordinator):
    """Coordinator for MQTT Vacuum Camera."""

    def __init__(
        self,
        hass,
        device_info,
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
        self.device_info = device_info
        self.shared, self.file_name = self._init_shared_data(vacuum_topic, device_info)
        self.connector = ValetudoConnector(vacuum_topic, hass, self.shared)

    @staticmethod
    def _init_shared_data(mqtt_listen_topic: str, device_info):
        """Initialize the shared data."""
        manager, shared, file_name = None, None, None
        if mqtt_listen_topic:
            manager = CameraSharedManager(
                mqtt_listen_topic.split("/")[1].lower(), device_info
            )
            shared = manager.get_instance()
            file_name = shared.file_name
            _LOGGER.debug(f"Camera {file_name} Starting up..")
        return shared, file_name

    async def _async_setup(self):
        """Set up the coordinator."""
        self._device = self.device_info
        _LOGGER.info(f"Setting up coordinator for {self.file_name}.")
        # Ensure subscription to MQTT topics
        await self.connector.async_subscribe_to_topics()

    async def _async_update_data(self, process: bool = True):
        """Fetch data from the MQTT topics."""
        try:
            async with async_timeout.timeout(10):
                # Fetch and process data from the MQTT connector
                return await self.connector.update_data(process)
        except ConfigEntryAuthFailed as err:
            raise ConfigEntryAuthFailed from err
        except Exception as err:
            _LOGGER.error(f"Error communicating with MQTT or processing data: {err}")
            raise UpdateFailed(f"Error communicating with MQTT: {err}")

    async def async_will_remove_from_hass(self):
        """Handle cleanup when the coordinator is removed."""
        _LOGGER.info(f"Cleaning up {self.file_name} coordinator.")
        await self.connector.async_unsubscribe_from_topics()


class MQTTCameraSubEntity(CoordinatorEntity):
    """An entity using CoordinatorEntity.

    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass
      available

    """

    def __init__(self, coordinator, idx):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, context=idx)
        self.idx = idx

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.coordinator.data[self.idx]["state"]
        self.async_write_ha_state()

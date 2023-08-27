import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr

_LOGGER: logging.Logger = logging.getLogger(__name__)


def get_device_info(config_entry_id: str, hass: HomeAssistant) -> str:
    """
    Fetches the vacuum's entity ID and Device from the
    entity registry and device registry.
    """
    vacuum_entity_id = er.async_resolve_entity_id(er.async_get(hass), config_entry_id)

    if not vacuum_entity_id:
        _LOGGER.error("Unable to lookup vacuum's entity ID. Was it removed?")
        return None

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    vacuum_device = device_registry.async_get(
        entity_registry.async_get(vacuum_entity_id).device_id
    )

    if not vacuum_device:
        _LOGGER.error("Unable to locate vacuum's device ID. Was it removed?")
        return None

    return (vacuum_entity_id, vacuum_device)

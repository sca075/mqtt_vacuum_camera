"""MQTT Vacuum Camera.
Version: 2024.11.0"""

import logging
import os

from homeassistant import config_entries, core
from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    SERVICE_RELOAD,
    Platform,
)
from homeassistant.core import ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers.reload import async_register_admin_service
from homeassistant.helpers.storage import STORAGE_DIR

from .common import (
    generate_service_data_clean_segments,
    generate_service_data_clean_zone,
    generate_service_data_go_to,
    get_vacuum_device_info,
    get_vacuum_mqtt_topic,
    get_entity_id,
    get_device_info_from_entity_id,
    is_rand256_vacuum,
    update_options,
)
from .const import (
    CAMERA_STORAGE,
    CONF_VACUUM_CONFIG_ENTRY_ID,
    CONF_VACUUM_CONNECTION_STRING,
    CONF_VACUUM_IDENTIFIERS,
    DOMAIN,
)
from .coordinator import MQTTVacuumCoordinator
from .utils.files_operations import (
    async_clean_up_all_auto_crop_files,
    async_get_translations_vacuum_id,
    async_rename_room_description,
)

PLATFORMS = [Platform.CAMERA, Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def options_update_listener(hass: core.HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_setup_entry(hass: core.HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""

    async def _reload_config(call: ServiceCall) -> None:
        """Reload the camera platform for all entities in the integration."""
        _LOGGER.debug(f"Reloading the config entry for all {DOMAIN} entities")
        # Retrieve all config entries associated with the DOMAIN
        camera_entries = hass.config_entries.async_entries(DOMAIN)

        # Iterate over each config entry and check if it's LOADED
        for camera_entry in camera_entries:
            if camera_entry.state == ConfigEntryState.LOADED:
                _LOGGER.debug(f"Unloading entry: {camera_entry.entry_id}")
                await async_unload_entry(hass, camera_entry)

                _LOGGER.debug(f"Reloading entry: {camera_entry.entry_id}")
                await async_setup_entry(hass, camera_entry)
            else:
                _LOGGER.debug(
                    f"Skipping entry {camera_entry.entry_id} as it is NOT_LOADED"
                )

        # Optionally, trigger other reinitialization steps if needed
        hass.bus.async_fire(f"event_{DOMAIN}_reloaded", context=call.context)

    async def vacuum_clean_segments(call: ServiceCall) -> None:
        """Vacuum Clean Segments (rooms) Action"""
        try:
            # Retrieve coordinates
            segments_lists = call.data.get("segments")
            repeats = call.data.get("repeats")

            # Attempt to get entity_id or device_id
            entity_ids = call.data.get("entity_id")
            device_ids = call.data.get("device_id")

            service_data = generate_service_data_clean_segments(
                coordinator=data_coordinator,
                entity_id=entity_ids,
                device_id=device_ids,
                segments=segments_lists,
                repeat=repeats,
                hass=hass,
            )
            _LOGGER.debug(f">>>>>> Service data: {service_data}")
            if not service_data:
                raise ServiceValidationError("No Service data generated. Aborting!")
            # elif not service_data["have_rooms"]:
            #     raise ServiceValidationError("No rooms found in the vacuum map.")
            else:
                try:
                    await data_coordinator.connector.publish_to_broker(
                        service_data["topic"],
                        service_data["payload"],
                    )
                except Exception as e:
                    _LOGGER.warning(f"Error sending command to vacuum: {e}")
                    return
                hass.bus.async_fire(
                    f"event_{DOMAIN}.vacuum_clean_zone",
                    {
                        "topic": service_data["topic"],
                        "zones": segments_lists,
                        "repeats": repeats,
                    },
                    context=call.context,
                )
        except KeyError as e:
            _LOGGER.error(f"Missing required parameter: {e}")

    async def vacuum_clean_zone(call: ServiceCall) -> None:
        """Vacuum Zone Clean Action"""
        try:
            # Retrieve coordinates
            zone_lists = call.data.get("zone")
            zone_ids = call.data.get("zone_ids")
            repeats = call.data.get("repeats")

            if zone_ids:
                zone_lists = zone_ids

            # Attempt to get entity_id or device_id
            entity_ids = call.data.get("entity_id")
            device_ids = call.data.get("device_id")

            service_data = generate_service_data_clean_zone(
                entity_id=entity_ids,
                device_id=device_ids,
                zones=zone_lists,
                repeat=repeats,
                hass=hass,
            )
            if not service_data:
                _LOGGER.warning("No Service data generated. Aborting!")
                return
            try:
                await data_coordinator.connector.publish_to_broker(
                    service_data["topic"],
                    service_data["payload"],
                )
            except Exception as e:
                _LOGGER.warning(f"Error sending command to vacuum: {e}")
                return
            hass.bus.async_fire(
                f"event_{DOMAIN}.vacuum_clean_zone",
                {
                    "topic": service_data["topic"],
                    "zones": zone_lists,
                    "repeats": repeats,
                },
                context=call.context,
            )
        except KeyError as e:
            _LOGGER.error(f"Missing required parameter: {e}")

    async def vacuum_goto(call: ServiceCall) -> None:
        """Vacuum Go To Action"""
        try:
            # Retrieve coordinates
            spot_id = call.data.get("spot_id")
            if not spot_id:
                x_coord = call.data["x_coord"]
                y_coord = call.data["y_coord"]
                spot_id = None
            else:
                x_coord = None
                y_coord = None

            # Attempt to get entity_id or device_id
            entity_ids = call.data.get("entity_id")
            device_ids = call.data.get("device_id")

            service_data = generate_service_data_go_to(
                entity_ids, device_ids, x_coord, y_coord, spot_id, hass
            )
            if not service_data:
                _LOGGER.warning("No Service data generated. Aborting!")
                return
            try:
                await data_coordinator.connector.publish_to_broker(
                    service_data["topic"],
                    service_data["payload"],
                )
            except Exception as e:
                _LOGGER.warning(f"Error sending command to vacuum: {e}")
                return
            hass.bus.async_fire(
                f"event_{DOMAIN}.vacuum_go_to",
                {"topic": service_data["topic"], "x": x_coord, "y": y_coord},
                context=call.context,
            )
        except KeyError as e:
            _LOGGER.error(f"Missing required parameter: {e}")

    async def vacuum_map_save(call: ServiceCall) -> None:
        """Vacuum Map Save Action"""
        try:
            # Attempt to get entity_id or device_id
            entity_ids = call.data.get("entity_id")
            device_ids = call.data.get("device_id")

            vacuum_entity_ids = get_entity_id(entity_ids, device_ids, hass)[0]
            base_topic = get_vacuum_mqtt_topic(vacuum_entity_ids, hass)
            device_info = get_device_info_from_entity_id(vacuum_entity_ids, hass)
            is_a_rand256 = is_rand256_vacuum(device_info)

            map_name = call.data.get("map_name")
            if not map_name:
                raise ServiceValidationError("A map name is required to save the map.")
            if is_a_rand256:
                service_data = {
                    "topic": f"{base_topic}/custom_command",
                    "payload": {
                        "command": "store_map",
                        "name": map_name,
                    },
                }
            else:
                raise ServiceValidationError(
                    "This feature is only available for rand256 vacuums."
                )
            try:
                await data_coordinator.connector.publish_to_broker(
                    service_data["topic"],
                    service_data["payload"],
                )
            except Exception as e:
                _LOGGER.warning(f"Error sending command to vacuum: {e}")
                return
            hass.bus.async_fire(
                f"event_{DOMAIN}.vacuum_map_save",
                {"topic": service_data["topic"]},
                context=call.context,
            )
        except KeyError as e:
            _LOGGER.error(f"Missing required parameter: {e}")

    async def vacuum_map_load(call: ServiceCall) -> None:
        """Vacuum Map Load Action"""
        try:
            # Attempt to get entity_id or device_id
            entity_ids = call.data.get("entity_id")
            device_ids = call.data.get("device_id")

            vacuum_entity_ids = get_entity_id(entity_ids, device_ids, hass)[0]
            base_topic = get_vacuum_mqtt_topic(vacuum_entity_ids, hass)
            device_info = get_device_info_from_entity_id(vacuum_entity_ids, hass)
            is_a_rand256 = is_rand256_vacuum(device_info)

            map_name = call.data.get("map_name")
            if not map_name:
                raise ServiceValidationError("A map name is required to load the map.")
            if is_a_rand256:
                service_data = {
                    "topic": f"{base_topic}/custom_command",
                    "payload": {
                        "command": "load_map",
                        "name": map_name,
                    },
                }
            else:
                raise ServiceValidationError(
                    "This feature is only available for rand256 vacuums."
                )
            try:
                await data_coordinator.connector.publish_to_broker(
                    service_data["topic"],
                    service_data["payload"],
                )
            except Exception as e:
                _LOGGER.warning(f"Error sending command to vacuum: {e}")
                return
            hass.bus.async_fire(
                f"event_{DOMAIN}.vacuum_map_load",
                {"topic": service_data["topic"]},
                context=call.context,
            )
            await hass.services.async_call(DOMAIN, "reset_trims")
        except KeyError as e:
            _LOGGER.error(f"Missing required parameter: {e}")

    async def reset_trims(call: ServiceCall) -> None:
        """Action Reset Map Trims."""
        _LOGGER.debug(f"Resetting trims for {DOMAIN}")
        await async_clean_up_all_auto_crop_files(hass)
        await hass.services.async_call(DOMAIN, "reload")
        hass.bus.async_fire(f"event_{DOMAIN}_reset_trims", context=call.context)

    # Register Services
    hass.services.async_register(DOMAIN, "reset_trims", reset_trims)
    if not hass.services.has_service(DOMAIN, SERVICE_RELOAD):
        async_register_admin_service(hass, DOMAIN, SERVICE_RELOAD, _reload_config)
    hass.services.async_register(DOMAIN, "vacuum_go_to", vacuum_goto)
    hass.services.async_register(DOMAIN, "vacuum_clean_zone", vacuum_clean_zone)
    hass.services.async_register(DOMAIN, "vacuum_clean_segments", vacuum_clean_segments)
    hass.services.async_register(DOMAIN, "vacuum_map_save", vacuum_map_save)
    hass.services.async_register(DOMAIN, "vacuum_map_load", vacuum_map_load)

    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(entry.data)

    vacuum_entity_id, vacuum_device = get_vacuum_device_info(
        hass_data[CONF_VACUUM_CONFIG_ENTRY_ID], hass
    )

    if not vacuum_entity_id:
        raise ConfigEntryNotReady(
            "Unable to lookup vacuum's entity ID. Was it removed?"
        )

    mqtt_topic_vacuum = get_vacuum_mqtt_topic(vacuum_entity_id, hass)
    if not mqtt_topic_vacuum:
        raise ConfigEntryNotReady("MQTT was not ready yet, automatically retrying")

    is_rand256 = is_rand256_vacuum(vacuum_device)

    data_coordinator = MQTTVacuumCoordinator(hass, entry, mqtt_topic_vacuum, is_rand256)

    hass_data.update(
        {
            CONF_VACUUM_CONNECTION_STRING: mqtt_topic_vacuum,
            CONF_VACUUM_IDENTIFIERS: vacuum_device.identifiers,
            CONF_UNIQUE_ID: entry.unique_id,
            "coordinator": data_coordinator,
            "is_rand256": is_rand256,
        }
    )

    # Registers update listener to update config entry when options are updated.
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)
    # Store a reference to the unsubscribe function to clean up if an entry is unloaded.
    hass_data["unsub_options_update_listener"] = unsub_options_update_listener
    hass.data[DOMAIN][entry.entry_id] = hass_data
    if bool(hass_data.get("is_rand256")):
        await hass.async_create_task(
            hass.config_entries.async_forward_entry_setups(entry, ["camera", "sensor"])
        )
    else:
        await hass.async_create_task(
            hass.config_entries.async_forward_entry_setups(entry, ["camera"])
        )

    return True


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    if bool(hass.data[DOMAIN][entry.entry_id]["is_rand256"]):
        unload_platform = PLATFORMS
    else:
        unload_platform = [Platform.CAMERA]
    _LOGGER.debug(f"Platforms to unload: {unload_platform}")
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, unload_platform
    ):
        # Remove config entry from domain.
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        entry_data["unsub_options_update_listener"]()
        # Remove services
        hass.services.async_remove(DOMAIN, "reset_trims")
        hass.services.async_remove(DOMAIN, SERVICE_RELOAD)
        hass.services.async_remove(DOMAIN, "vacuum_go_to")
        hass.services.async_remove(DOMAIN, "vacuum_clean_zone")
        hass.services.async_remove(DOMAIN, "vacuum_clean_segments")
        hass.services.async_remove(DOMAIN, "vacuum_map_save")
        hass.services.async_remove(DOMAIN, "vacuum_map_load")
    return unload_ok


# noinspection PyCallingNonCallable
async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    """Set up the MQTT Camera Custom component from yaml configuration."""

    async def handle_homeassistant_stop(event):
        """Handle Home Assistant stop event."""
        _LOGGER.info("Home Assistant is stopping. Writing down the rooms data.")
        storage = hass.config.path(STORAGE_DIR, CAMERA_STORAGE)
        if not os.path.exists(storage):
            _LOGGER.debug(f"Storage path: {storage} do not exists. Aborting!")
            return False
        vacuum_entity_id = await async_get_translations_vacuum_id(storage)
        if not vacuum_entity_id:
            _LOGGER.debug("No vacuum room data found. Aborting!")
            return False
        _LOGGER.debug(f"Writing down the rooms data for {vacuum_entity_id}.")
        result = await async_rename_room_description(hass, vacuum_entity_id)
        await hass.async_block_till_done()
        return True

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_FINAL_WRITE, handle_homeassistant_stop
    )

    # Make sure MQTT integration is enabled and the client is available
    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration is not available")
        return False
    hass.data.setdefault(DOMAIN, {})
    return True

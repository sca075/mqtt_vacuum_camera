"""
MQTT Vacuum Camera.
Version: 2025.10.0
"""

from functools import partial
from pathlib import Path
from typing import Any
import zipfile

from homeassistant import config_entries, core
from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_RELOAD,
    Platform,
)
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.reload import async_register_admin_service
from valetudo_map_parser import get_default_font_path
from valetudo_map_parser.config.shared import CameraShared, CameraSharedManager

from .common import (
    get_camera_device_info,
    get_vacuum_device_info,
    get_vacuum_mqtt_topic,
    is_congaduto_vacuum,
    is_rand256_vacuum,
    update_options,
)
from .const import (
    CONF_VACUUM_CONFIG_ENTRY_ID,
    CONF_VACUUM_CONNECTION_STRING,
    CONF_VACUUM_IDENTIFIERS,
    DISABLE_MAP_ELEMENTS,
    DOMAIN,
    LOGGER,
)
from .coordinator import MQTTVacuumCoordinator
from .types import CoordinatorConfig
from .utils.camera.camera_services import (
    camera_select_floor,
    camera_update_floor_data,
    obstacle_view,
    reload_camera_config,
    reset_trims,
)
from .utils.connection.connector import ValetudoConnector
from .utils.files_operations import async_get_active_user_language
from .utils.thread_pool import ThreadPoolManager
from .utils.vacuum.mqtt_vacuum_services import (
    async_register_vacuums_services,
    async_remove_vacuums_services,
)

PLATFORMS = [Platform.CAMERA, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)  # pylint: disable=invalid-name


def init_shared_data(
    _hass: core.HomeAssistant,
    mqtt_listen_topic: str,
    device_info: DeviceInfo,
) -> tuple[CameraShared, str]:
    """
    Initialize the shared data.
    Raises ValueError if mqtt_listen_topic is empty.
    """
    if not mqtt_listen_topic:
        raise ValueError("mqtt_listen_topic is required to initialize shared data")

    file_name = mqtt_listen_topic.split("/")[1].lower()
    shared_manager = CameraSharedManager(file_name, dict(device_info))
    shared = shared_manager.get_instance()
    shared.vacuum_status_font = f"{get_default_font_path()}/FiraSans.ttf"
    return shared, file_name


async def start_up_mqtt(
    hass, vacuum_topic: str, is_rand256: bool, shared: CameraShared
) -> ValetudoConnector:
    """
    Initialize the MQTT Connector.
    """
    connector = ValetudoConnector(vacuum_topic, hass, shared, is_rand256)
    await connector.async_subscribe_to_topics()
    return connector


async def init_coordinator(hass, entry, vacuum_topic, is_rand256, is_conga):
    """Initialize the coordinator with configuration."""
    device_info: DeviceInfo = get_camera_device_info(hass, entry)
    shared, _ = init_shared_data(hass, vacuum_topic, device_info)
    shared.user_language = await async_get_active_user_language(hass)
    shared.is_rand = is_rand256
    shared.is_conga = is_conga
    connector = await start_up_mqtt(hass, vacuum_topic, is_rand256, shared)

    config = CoordinatorConfig(
        hass=hass,
        device_entity=entry,
        vacuum_topic=vacuum_topic,
        is_rand256=is_rand256,
        connector=connector,
        shared=shared,
    )
    coordinator_entity = MQTTVacuumCoordinator(config)
    return coordinator_entity


async def options_update_listener(hass: core.HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_setup_entry(hass: core.HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""

    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(entry.data)

    device_info = get_vacuum_device_info(hass_data[CONF_VACUUM_CONFIG_ENTRY_ID], hass)

    if device_info is None:
        raise ConfigEntryNotReady(
            "Vacuum device not found. Please check your vacuum integration."
        )

    vacuum_entity_id, vacuum_device = device_info

    if not vacuum_entity_id:
        raise ConfigEntryNotReady(
            "Unable to lookup vacuum's entity ID. Was it removed?"
        )

    mqtt_topic_vacuum = get_vacuum_mqtt_topic(vacuum_entity_id, hass)
    if not mqtt_topic_vacuum:
        raise ConfigEntryNotReady("MQTT was not ready yet, automatically retrying")

    is_rand256 = is_rand256_vacuum(vacuum_device)
    is_conga = is_congaduto_vacuum(vacuum_device)

    data_coordinator = await init_coordinator(
        hass, entry, mqtt_topic_vacuum, is_rand256, is_conga
    )

    hass_data.update(
        {
            CONF_VACUUM_CONNECTION_STRING: mqtt_topic_vacuum,
            CONF_VACUUM_IDENTIFIERS: vacuum_device.identifiers,
            CONF_UNIQUE_ID: entry.unique_id,
            "coordinator": data_coordinator,
            "is_rand256": is_rand256,
            "file_name": data_coordinator.context.file_name,
        }
    )
    # Register Services
    if not hass.services.has_service(DOMAIN, SERVICE_RELOAD):
        async_register_admin_service(
            hass, DOMAIN, SERVICE_RELOAD, partial(reload_camera_config, hass=hass)
        )
        hass.services.async_register(
            DOMAIN, "reset_trims", partial(reset_trims, hass=hass)
        )
        hass.services.async_register(
            DOMAIN, "obstacle_view", partial(obstacle_view, hass=hass)
        )
        hass.services.async_register(
            DOMAIN, "camera_select_floor", partial(camera_select_floor, hass=hass)
        )
        hass.services.async_register(
            DOMAIN,
            "camera_update_floor_data",
            partial(camera_update_floor_data, hass=hass),
        )
        await async_register_vacuums_services(hass, data_coordinator)
    # Registers update listener to update config entry when options are updated.
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)
    # Store a reference to the unsubscribe function to clean up if an entry is unloaded.
    hass_data["unsub_options_update_listener"] = unsub_options_update_listener
    hass.data[DOMAIN][entry.entry_id] = hass_data
    if bool(hass_data.get("is_rand256")):
        await hass.config_entries.async_forward_entry_setups(
            entry, ["camera", "sensor"]
        )
    else:
        await hass.config_entries.async_forward_entry_setups(entry, ["camera"])

    return True


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    if bool(hass.data[DOMAIN][entry.entry_id]["is_rand256"]):
        unload_platform = PLATFORMS
    else:
        unload_platform = [Platform.CAMERA]
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, unload_platform
    ):
        # Remove config entry from domain.
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        entry_data["unsub_options_update_listener"]()

        # Shutdown thread pool for this entry only
        # Use file_name (from MQTT topic) instead of entry.entry_id to match pool creation
        file_name = entry_data.get("file_name")
        if file_name:
            LOGGER.debug(
                "Shutting down thread pools using file_name: %s (entry_id: %s)",
                file_name,
                entry.entry_id,
            )
            thread_pool = ThreadPoolManager.get_instance(file_name)
            await thread_pool.shutdown_instance()
        else:
            # Backward compatibility: if file_name not in entry_data (old installations)
            # Camera entity cleanup will handle thread pool shutdown
            LOGGER.debug(
                "file_name not found in entry_data, relying on camera entity cleanup"
            )

        # Remove services
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "reset_trims")
            hass.services.async_remove(DOMAIN, "obstacle_view")
            hass.services.async_remove(DOMAIN, "camera_select_floor")
            hass.services.async_remove(DOMAIN, "camera_update_floor_data")
            hass.services.async_remove(DOMAIN, SERVICE_RELOAD)
            await async_remove_vacuums_services(hass)
    return unload_ok


# noinspection PyCallingNonCallable
async def async_setup(hass: core.HomeAssistant, _config: dict) -> bool:
    """Set up the MQTT Camera Custom component from YAML configuration."""

    async def handle_homeassistant_stop(_event):
        """Handle Home Assistant stop event."""
        LOGGER.info("Home Assistant is stopping. Writing down the rooms data.")
        await ThreadPoolManager.shutdown_all()
        LOGGER.info("Home Assistant stopped. Mqtt Vacuum Camera exit complete.")
        return True

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, handle_homeassistant_stop)

    # Make sure MQTT integration is enabled and the client is available
    if not await mqtt.async_wait_for_mqtt_client(hass):
        LOGGER.error("MQTT integration is not available")
        return False
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_migrate_entry(hass, config_entry: config_entries.ConfigEntry):
    """Migrate old entry."""
    # pylint: disable=too-many-return-statements,too-many-statements
    # Migration functions are inherently complex due to multiple version checks
    # as it loads at every rebot, the logs stay in the migration steps
    if config_entry.version == 3.1:
        LOGGER.debug("Migrating config entry from version %s", config_entry.version)
        old_data = {**config_entry.data}
        new_data = {"vacuum_config_entry": old_data["vacuum_config_entry"]}
        LOGGER.debug(dict(new_data))
        old_options = {**config_entry.options}
        if len(old_options) != 0:
            tmp_option: dict[str, Any] = {
                "trims_data": {
                    "trim_left": 0,
                    "trim_up": 0,
                    "trim_right": 0,
                    "trim_down": 0,
                },
            }
            new_options = await update_options(old_options, tmp_option)
            del tmp_option  # Clear for mypy
            LOGGER.debug("Migration data: %s", dict(new_options))
            hass.config_entries.async_update_entry(
                config_entry, version=3.2, data=new_data, options=new_options
            )
            LOGGER.info(
                "Migration to config entry version %s successful", config_entry.version
            )
            return True
    if config_entry.version == 3.2:
        LOGGER.info("Migration to config entry version %s successful", 3.2)
        old_data = {**config_entry.data}
        new_data = {"vacuum_config_entry": old_data["vacuum_config_entry"]}
        LOGGER.debug(dict(new_data))
        old_options = {**config_entry.options}
        if len(old_options) != 0:
            tmp_option: dict[str, Any] = {  # type: ignore[no-redef]
                **DISABLE_MAP_ELEMENTS,
            }
            new_options = await update_options(old_options, tmp_option)
            del tmp_option  # Clear for mypy
            LOGGER.debug("Migration data: %s", dict(new_options))
            hass.config_entries.async_update_entry(
                config_entry, version=3.3, data=new_data, options=new_options
            )
            LOGGER.info(
                "Migration to config entry version %s successful",
                config_entry.version,
            )
            return True
    if config_entry.version == 3.3:
        LOGGER.info("Migrating config entry from version %s", config_entry.version)

        # Restore translation files from backup ZIP (run in executor to avoid blocking)
        def restore_translations():
            """Restore translation files from backup ZIP with path traversal protection."""
            base_dir = Path(__file__).parent.resolve()
            backup_zip = base_dir / "translations_backup.zip"

            if not backup_zip.exists():
                LOGGER.warning(
                    "Translation backup file not found, skipping restoration"
                )
                return False

            try:
                LOGGER.info("Restoring translation files from backup")

                with zipfile.ZipFile(backup_zip, "r") as zip_ref:
                    for member in zip_ref.infolist():
                        name = member.filename

                        # Block absolute paths
                        if Path(name).is_absolute():
                            LOGGER.error(
                                "Security: Blocked absolute path in zip: %s", name
                            )
                            return False

                        # Resolve the destination path
                        dest = (base_dir / name).resolve()

                        # Ensure extraction stays within target directory
                        if not dest.is_relative_to(base_dir):
                            LOGGER.error(
                                "Security: Blocked path traversal attempt in zip: %s",
                                name,
                            )
                            return False

                        # Extract this member safely
                        zip_ref.extract(member, base_dir)

                LOGGER.info("Translation files restored successfully")

                # Only delete backup on successful restoration
                if backup_zip.exists():
                    backup_zip.unlink()

                return True

            except (OSError, zipfile.BadZipFile, ValueError) as e:
                LOGGER.error("Failed to restore translation files: %s", e)
                return False

        # Run the blocking I/O in an executor
        await hass.async_add_executor_job(restore_translations)

        old_data = {**config_entry.data}
        new_data = {"vacuum_config_entry": old_data["vacuum_config_entry"]}
        LOGGER.debug(dict(new_data))
        old_options = {**config_entry.options}
        if len(old_options) != 0:
            # Remove deprecated options
            old_options.pop("enable_www_snapshots", None)
            old_options.pop("get_svg_file", None)
            # Add new options with defaults
            tmp_option: dict[str, Any] = {  # type: ignore[no-redef]
                "robot_size": 25,
            }
            # Merge tmp_option into old_options
            old_options.update(tmp_option)
            del tmp_option  # Clear for mypy
            # Now process with update_options
            new_options = await update_options(old_options, {})
            LOGGER.debug("Migration data: %s", dict(new_options))
            hass.config_entries.async_update_entry(
                config_entry, version=3.4, data=new_data, options=new_options
            )
            LOGGER.info(
                "Migration to config entry version %s successful",
                config_entry.version,
            )
            return True

        LOGGER.error(
            "Migration failed: No options found in config entry. Please reconfigure the camera."
        )
        return False
    if config_entry.version == 3.4:
        LOGGER.info("Migrating config entry from version %s", config_entry.version)
        old_data = {**config_entry.data}
        new_data = {"vacuum_config_entry": old_data["vacuum_config_entry"]}
        LOGGER.debug(dict(new_data))
        old_options = {**config_entry.options}
        if len(old_options) != 0:
            # Add carpet mode and floor materials options
            tmp_option: dict[str, Any] = {  # type: ignore[no-redef]
                "disable_carpets": False,
                "disable_material_overlay": False,
                "color_carpet": [255, 192, 203],
                "color_material_wood": [40, 40, 40],
                "color_material_tile": [40, 40, 40],
                "alpha_carpet": 255.0,
                "alpha_material_wood": 38.0,
                "alpha_material_tile": 45.0,
            }
            new_options = await update_options(old_options, tmp_option)
            del tmp_option  # Clear for mypy
            LOGGER.debug("Migration data: %s", dict(new_options))
            hass.config_entries.async_update_entry(
                config_entry, version=3.5, data=new_data, options=new_options
            )
            LOGGER.info(
                "Migration to config entry version %s successful",
                config_entry.version,
            )
            return True

        LOGGER.error(
            "Migration failed: No options found in config entry. Please reconfigure the camera."
        )
        return False
    if config_entry.version == 3.5:
        LOGGER.info("Migrating config entry from version %s", config_entry.version)
        old_data = {**config_entry.data}
        new_data = {"vacuum_config_entry": old_data["vacuum_config_entry"]}
        old_options = {**config_entry.options}
        if len(old_options) != 0:
            # Add mop mode, obstacle link, and floor management options
            tmp_option: dict[str, Any] = {  # type: ignore[no-redef]
                "mop_path_width": 10,
                "color_mop_move": [238, 247, 255],
                "alpha_mop_move": 100.0,
                "obstacle_link_protocol": "http",
                "obstacle_link_port": 80,
                "obstacle_link_ip": "",
                "floors_data": {},
                "current_floor": "floor_0",
            }
            new_options = await update_options(old_options, tmp_option)
            del tmp_option  # Clear for mypy
            LOGGER.debug("Migration data: %s", dict(new_options))
            hass.config_entries.async_update_entry(
                config_entry, version=3.6, data=new_data, options=new_options
            )
            LOGGER.info(
                "Migration to config entry version %s successful",
                config_entry.version,
            )
            return True

        LOGGER.error(
            "Migration failed: No options found in config entry. Please reconfigure the camera."
        )
        return False
    if config_entry.version == 3.6:
        LOGGER.info("Migrating config entry from version %s", config_entry.version)
        old_data = {**config_entry.data}
        new_data = {"vacuum_config_entry": old_data["vacuum_config_entry"]}
        old_options = {**config_entry.options}
        if len(old_options) != 0:
            # Add image format option
            tmp_option: dict[str, Any] = {  # type: ignore[no-redef]
                "def_context_type": "jpeg",
            }
            new_options = await update_options(old_options, tmp_option)
            del tmp_option  # Clear for mypy
            LOGGER.debug("Migration data: %s", dict(new_options))
            hass.config_entries.async_update_entry(
                config_entry, version=3.7, data=new_data, options=new_options
            )
            LOGGER.info(
                "Migration to config entry version %s successful",
                config_entry.version,
            )
            return True

        LOGGER.error(
            "Migration failed: No options found in config entry. Please reconfigure the camera."
        )
        return False
    return True

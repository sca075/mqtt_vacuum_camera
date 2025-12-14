"""
Type definitions and dataclasses for MQTT Vacuum Camera integration.
Version: 2025.12.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


@dataclass
class GoToRequest:
    """Request data for vacuum go-to command."""

    hass: HomeAssistant
    entity_id: str | None = None
    device_id: str | None = None
    x: int | None = None
    y: int | None = None
    spot_id: str | None = None


@dataclass
class CleanZoneRequest:
    """Request data for vacuum zone cleaning command."""

    hass: HomeAssistant
    zones: list
    entity_id: str | None = None
    device_id: str | None = None
    repeat: int = 1
    after_cleaning: str = "Base"


@dataclass
class CleanSegmentsRequest:
    """Request data for vacuum segment cleaning command."""

    hass: HomeAssistant
    coordinator: Any
    segments: list
    entity_id: str | None = None
    device_id: str | None = None
    repeat: int = 1
    after_cleaning: str = "Base"


@dataclass
class CoordinatorConfig:
    """Configuration for MQTT Vacuum Coordinator."""

    hass: HomeAssistant
    device_entity: ConfigEntry
    vacuum_topic: str
    is_rand256: bool = False
    connector: Optional[Any] = None
    shared: Optional[Any] = None
    polling_interval: timedelta = field(default_factory=lambda: timedelta(seconds=10))


# ============================================================================
# Camera Entity Dataclasses
# ============================================================================


@dataclass
class CameraContext:
    """Core Home Assistant and coordinator context for camera."""

    hass: HomeAssistant
    shared: Any  # CameraShared
    file_name: str
    coordinator: Any  # MQTTVacuumCoordinator


@dataclass
class CameraDeviceInfo:
    """Camera device identity and metadata."""

    model: str = "MQTT Vacuums"
    brand: str = "MQTT Vacuum Camera"
    name: str = "Camera"
    unique_id: Optional[str] = None
    identifiers: Optional[tuple] = None


@dataclass
class CameraMQTTConfig:
    """MQTT connection configuration for camera."""

    topic: str
    connector: Any  # ValetudoConnector


@dataclass
class CameraPathsConfig:
    """File system paths for camera storage."""

    homeassistant_path: str
    storage_path: str
    log_file: str


@dataclass
class CameraImageState:
    """Current image state and dimensions."""

    main_image: Optional[bytes] = None
    width: Optional[int] = None
    height: Optional[int] = None
    json_data: Optional[dict] = None


@dataclass
class CameraProcessors:
    """Image processing and management components."""

    processor: Any  # CameraProcessor
    decompression: Any  # DecompressionManager
    thread_pool: Any  # ThreadPoolManager
    colours: Any  # ColorsManagement
    obstacle_view: Any  # ObstacleView


@dataclass
class CameraSettings:
    """Camera entity settings and configuration."""

    is_on: bool = True
    should_poll: bool = False
    frame_interval: float = 6.0
    event_listener: Optional[Callable] = None

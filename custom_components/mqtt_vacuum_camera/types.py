"""
Type definitions and dataclasses for MQTT Vacuum Camera integration.
Version: 2025.11.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Optional

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

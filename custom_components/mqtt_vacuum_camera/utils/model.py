"""
Data models for MQTT Vacuum Camera integration.
Simple data structure placeholders.
Version: 2025.6.0
"""

from typing import Any, Dict, Optional, TypedDict
from PIL import Image


class CameraImageData(TypedDict, total=False):
    """Camera data structure - just placeholders."""

    # Core data
    pil_image: Optional[Image.Image]
    shared_data: Any
    thread_pool: Any

    # Basic info
    data_type: Optional[str]
    vacuum_topic: str

    # Map data
    segments: Optional[Dict[str, str]]
    destinations: Optional[Dict[str, Any]]
    parsed_json: Optional[Dict[str, Any]]

    # Vacuum state
    vacuum_status: Optional[str]
    vacuum_battery: Optional[int]
    vacuum_connection: Optional[bool]
    vacuum_position: Optional[Dict[str, float]]

    # Image info
    image_width: Optional[int]
    image_height: Optional[int]

    # Error handling
    error_message: Optional[str]
    success: bool


class SensorData(TypedDict, total=False):
    """ Sensor data structure - just placeholders. """

    # Vacuum state
    vacuum_status: Optional[str]
    vacuum_battery: Optional[int]
    vacuum_connection: Optional[bool]
    vacuum_position: Optional[Dict[str, float]]

    # Cleaning statistics
    cleaning_time: Optional[int]
    cleaning_area: Optional[float]
    total_cleaning_time: Optional[int]

    # Maintenance
    main_brush_left: Optional[int]
    side_brush_left: Optional[int]
    filter_left: Optional[int]
    sensor_dirty_left: Optional[int]

    # Map data
    segments: Optional[Dict[str, str]]
    destinations: Optional[Dict[str, Any]]

    # Error handling
    error_message: Optional[str]
    success: bool


class VacuumData(TypedDict, total=False):
    """Combined vacuum data structure with camera and sensor subkeys."""
    # Main structure
    vacuum_topic: str
    shared_data: Any

    # Substructures
    camera: CameraImageData
    sensors: SensorData

    # Error handling
    error_message: Optional[str]
    success: bool

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from PIL import Image


@dataclass
class CameraImageData:
    """Optimized structure for camera data."""

    pil_image: Optional[Image.Image] = None
    is_rand: bool = False
    shared_data: Any = None  # Should be typed if possible
    thread_pool: Any = None  # Should be typed if possible

    data_type: Optional[str] = None
    vacuum_topic: str = ""

    segments: Optional[Dict[str, str]] = field(default_factory=dict)
    destinations: Optional[Dict[str, Any]] = field(default_factory=dict)
    parsed_json: Optional[Dict[str, Any]] = field(default_factory=dict)

    vacuum_status: Optional[str] = None
    vacuum_battery: Optional[int] = None
    vacuum_connection: Optional[bool] = None
    vacuum_position: Optional[Dict[str, float]] = field(default_factory=dict)

    image_width: Optional[int] = None
    image_height: Optional[int] = None

    error_message: Optional[str] = None
    success: bool = True

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CameraImageData):
            return False
        return self.parsed_json == other.parsed_json


@dataclass
class SensorData:
    """Optimized structure for sensor data."""

    is_rand: bool = False
    vacuum_status: Optional[str] = None
    vacuum_battery: Optional[int] = None
    vacuum_connection: Optional[bool] = None
    vacuum_position: Optional[Dict[str, float]] = field(default_factory=dict)

    cleaning_time: Optional[int] = None
    cleaning_area: Optional[float] = None
    total_cleaning_time: Optional[int] = None

    main_brush_left: Optional[int] = None
    side_brush_left: Optional[int] = None
    filter_left: Optional[int] = None
    sensor_dirty_left: Optional[int] = None

    segments: Optional[Dict[str, str]] = field(default_factory=dict)
    destinations: Optional[Dict[str, Any]] = field(default_factory=dict)

    error_message: Optional[str] = None
    success: bool = True

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SensorData):
            return False
        return (
            self.vacuum_status == other.vacuum_status
            and self.vacuum_battery == other.vacuum_battery
            and self.cleaning_area == other.cleaning_area
        )


@dataclass
class VacuumData:
    camera: Optional[CameraImageData] = None
    sensors: Optional[SensorData] = None
    error_message: Optional[str] = None
    success: bool = True

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VacuumData):
            return False
        return self.camera == other.camera and self.sensors == other.sensors

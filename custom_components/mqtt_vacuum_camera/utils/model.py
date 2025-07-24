from dataclasses import dataclass, field, asdict
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
    is_streaming: bool = False
    error_message: Optional[str] = None
    success: bool = True

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CameraImageData):
            return False
        return self.parsed_json == other.parsed_json


@dataclass
class SensorData:
    """Structured and complete sensor data model."""

    # Maintenance
    mainBrush: int = 0
    sideBrush: int = 0
    filter_life: int = 0
    sensor: int = 0

    # Current cleaning session
    currentCleanTime: int = 0
    currentCleanArea: float = 0.0

    # Cumulative cleaning stats
    cleanTime: int = 0
    cleanArea: float = 0.0
    cleanCount: int = 0

    # Vacuum status
    battery: int = 0
    state: str = "unknown"

    # Last run stats
    last_run_start: int = 0
    last_run_end: int = 0
    last_run_duration: int = 0
    last_run_area: float = 0.0

    # Bin status
    last_bin_out: int = 0
    last_bin_full: int = 0

    # Map info
    last_loaded_map: str = "Default"
    robot_in_room: str = "Unsupported"

    # Metadata
    success: bool = True
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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

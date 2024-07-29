"""
Class Camera Shared.
Keep the data between the modules.
Version: v2024.08.0b0
"""

import asyncio

from custom_components.mqtt_vacuum_camera.types import Colors


class CameraShared(object):
    """
    CameraShared class to keep the data between the classes.
    Implements a kind of Thread Safe data shared area.
    """

    def __init__(self, file_name):
        self.frame_number: int = 0  # camera Frame number
        self.destinations: list = []  # MQTT rand destinations
        self.rand256_active_zone: list = []  # Active zone for rand256
        self.is_rand: bool = False  # MQTT rand data
        self._new_mqtt_message = False  # New MQTT message
        self.last_image = None  # Last image received
        self.image_size = None  # Image size
        self.image_auto_zoom: bool = False  # Auto zoom image
        self.image_zoom_lock_ratio: bool = True  # Zoom lock ratio
        self.image_ref_height: int = 0  # Image reference height
        self.image_ref_width: int = 0  # Image reference width
        self.image_aspect_ratio: str = "None"  # Change Image aspect ratio
        self.image_grab = True  # Grab image from MQTT
        self.image_rotate: int = 0  # Rotate image
        self.drawing_limit: float = 0.0  # Drawing CPU limit
        self.current_room = None  # Current room of rhe vacuum
        self.user_colors = Colors  # User base colors
        self.rooms_colors = Colors  # Rooms colors
        self.vacuum_battery = None  # Vacuum battery state
        self.vacuum_bat_charged: bool = True  # Vacuum charged and ready
        self.vacuum_connection = None  # Vacuum connection state
        self.vacuum_state = None  # Vacuum state
        self.charger_position = None  # Vacuum Charger position
        self.show_vacuum_state = None  # Show vacuum state on the map
        self.vacuum_status_font: str = (
            "custom_components/mqtt_vacuum_camera/utils/fonts/FiraSans.ttf"  # Font
        )
        self.vacuum_status_size: int = 50  # Vacuum status size
        self.vacuum_status_position: bool = True  # Vacuum status text image top
        self.snapshot_take = False  # Take snapshot
        self.vacuum_error = None  # Vacuum error
        self.vac_json_id = None  # Vacuum json id
        self.margins = "100"  # Image margins
        self.offset_top = 0  # Image offset top
        self.offset_down = 0  # Image offset down
        self.offset_left = 0  # Image offset left
        self.offset_right = 0  # Image offset right
        self.export_svg = False  # Export SVG
        self.svg_path = None  # SVG Export path
        self.enable_snapshots = False  # Enable snapshots
        self.file_name = file_name  # vacuum friendly name as File name
        self.attr_calibration_points = None  # Calibration points of the image
        self.map_rooms = None  # Rooms data from the vacuum
        self.map_pred_zones = None  # Predefined zones data
        self.map_pred_points = None  # Predefined points data
        self.map_new_path = None  # New path data
        self.map_old_path = None  # Old path data
        self.trim_crop_data = None
        self.user_language = None  # User language

    def update_user_colors(self, user_colors):
        """Update the user colors."""
        self.user_colors = user_colors

    def get_user_colors(self):
        """Get the user colors."""
        return self.user_colors

    def update_rooms_colors(self, user_colors):
        """Update the rooms colors."""
        self.rooms_colors = user_colors

    def get_rooms_colors(self):
        """Get the rooms colors."""
        return self.rooms_colors

    async def batch_update(self, **kwargs):
        """Batch update multiple attributes."""
        for key, value in kwargs.items():
            setattr(self, key, value)

    async def batch_get(self, *args):
        """Batch get multiple attributes."""
        return {key: getattr(self, key) for key in args}


class CameraSharedManager:
    def __init__(self, file_name):
        self._instances = {}
        self._lock = asyncio.Lock()
        self.file_name = file_name

    def get_instance(self):
        if self.file_name not in self._instances:
            self._instances[self.file_name] = CameraShared(self.file_name)
            self._instances[self.file_name].file_name = self.file_name
        return self._instances[self.file_name]

    async def update_instance(self, **kwargs):
        async with self._lock:
            instance = self.get_instance()
            await instance.batch_update(**kwargs)

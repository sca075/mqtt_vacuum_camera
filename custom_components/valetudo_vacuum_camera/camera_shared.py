"""
Class Camera Shared.
Keep the data between the modules.
Version 1.5.9-rc2
"""

import logging

from custom_components.valetudo_vacuum_camera.types import Colors

_LOGGER = logging.getLogger(__name__)


class CameraShared(object):
    """
    CameraShared class to keep the data between the classes.
    Implements a kind of Thread Safe data shared area.
    """

    def __init__(self):
        self.frame_number: int = 0  # camera Frame number
        self.destinations: list = []  # MQTT rand destinations
        self.is_rand: bool = False  # MQTT rand data
        self._new_mqtt_message = False  # New MQTT message
        self.last_image = None  # Last image received
        self.image_size = None  # Image size
        self.image_auto_zoom: bool = False  # Auto zoom image
        self.image_ref_height: int = 0  # Image reference height
        self.image_ref_width: int = 0  # Image reference width
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
        self.vacuum_status_size: int = 50  # Vacuum status size
        self.vacuum_status_position: bool = True  # Vacuum status text image top
        self.snapshot_take = False  # Take snapshot
        self.vacuum_error = None  # Vacuum error
        self.vac_json_id = None  # Vacuum json id
        self.margins = None  # Image margins
        self.export_svg = False  # Export SVG
        self.svg_path = None  # SVG Export path
        self.file_name = ""  # vacuum friendly name as File name
        self.attr_calibration_points = None  # Calibration points of the image
        self.map_rooms = None  # Rooms data from the vacuum
        self.map_pred_zones = None  # Predefined zones data
        self.map_pred_points = None  # Predefined points data
        self.map_new_path = None  # New path data
        self.map_old_path = None  # Old path data

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

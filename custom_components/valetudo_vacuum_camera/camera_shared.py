"""
Class Camera Shared.
Keep the data between the modules.
Version 1.5.7.1
"""

import logging

from custom_components.valetudo_vacuum_camera.types import Colors

_LOGGER = logging.getLogger(__name__)


class CameraShared(object):
    def __init__(self):
        self.frame_number: int = 0  # camera Frame number
        self.destinations: list = []  # MQTT rand destinations
        self.is_rand: bool = False  # MQTT rand data
        self._new_mqtt_message = False  # New MQTT message
        self._last_image = None  # Last image received
        self.image_size = None  # Image size
        self.image_grab = True  # Grab image from MQTT
        self.image_rotate: int = 0  # Rotate image
        self.drawing_limit: float = 0.0  # Drawing CPU limit
        self.current_room = None  # Current room of rhe vacuum
        self.user_colors = Colors  # User base colors
        self.rooms_colors = Colors  # Rooms colors
        self.vacuum_state = None  # Vacuum state
        self.charger_position = None  # Vacuum Charger position
        self.show_vacuum_state = None  # Show vacuum state on the map
        self.snapshot_take = False  # Take snapshot
        self.vacuum_error = None  # Vacuum error
        self.vac_json_id = None  # Vacuum json id
        self.margins = None  # Image margins
        self.export_svg = None  # Export SVG
        self.svg_path = None  # SVG Export path
        self.file_name = None  # vacuum friendly name as File name
        self.attr_calibration_points = None  # Calibration points of the image
        self.map_rooms = None  # Rooms data from the vacuum
        self.map_pred_zones = None  # Predefined zones data
        self.map_pred_points = None  # Predefined points data

    def update_user_colors(self, user_colors):
        self.user_colors = user_colors

    def get_user_colors(self):
        return self.user_colors

    def update_rooms_colors(self, user_colors):
        self.rooms_colors = user_colors

    def get_rooms_colors(self):
        return self.rooms_colors

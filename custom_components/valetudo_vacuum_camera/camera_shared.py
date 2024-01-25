"""
Class Camera Shared.
Keep the data between the modules.
Version 1.5.7
"""

import logging

from custom_components.valetudo_vacuum_camera.types import Colors

_LOGGER = logging.getLogger(__name__)


class CameraShared(object):
    def __init__(self):
        self.frame_number = 0
        self._new_mqtt_message = False
        self._last_image = None
        self.image_size = None
        self.image_grab = None
        self.current_room = None
        self.user_colors = Colors
        self.rooms_colors = Colors
        self.vacuum_state = None
        self.charger_position = None
        self.show_vacuum_state = None
        self.snapshot_take = False
        self.vacuum_error = None
        self.vac_json_id = None
        self.margins = None
        self.export_svg = None
        self.file_name = None
        self.image_rotate = None
        self.attr_calibration_points = None
        self.map_rooms = None
        self.map_pred_zones = None
        self.map_pred_points = None

    def update_user_colors(self, user_colors):
        self.user_colors = user_colors

    def get_user_colors(self):
        return self.user_colors

    def update_rooms_colors(self, user_colors):
        self.rooms_colors = user_colors

    def get_rooms_colors(self):
        return self.rooms_colors

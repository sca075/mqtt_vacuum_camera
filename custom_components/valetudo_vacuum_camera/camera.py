from __future__ import annotations

import logging
import json
import numpy as np
import math
import cv2
import requests
import voluptuous as vol
from datetime import timedelta
from typing import Optional
#from .connector import MQTTConnector

from homeassistant.components.camera import (Camera, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_NAME,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.util import Throttle

#_LOGGER: logging.Logger = logging.getLogger(__name__)
_LOGGER = logging.getLogger(__name__)

#CONF_VACUUM_CONNECTION_STRING = "vacuum_map"
#CONF_VACUUM_ENTITY_ID = "vacuum_entity"

#DEFAULT_NAME = "valetudo vacuum"
from .const import CONF_VACUUM_CONNECTION_STRING, CONF_VACUUM_ENTITY_ID, DEFAULT_NAME

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_VACUUM_CONNECTION_STRING): cv.string,
        vol.Required(CONF_VACUUM_ENTITY_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    async_add_entities([ValetudoCamera(hass, config)])


class ValetudoCamera(Camera):
    def __init__(self, hass, device_info):
        super().__init__()
        self.hass = hass
        self._name = device_info.get(CONF_NAME)
        self._vacuum_entity = device_info.get(CONF_VACUUM_ENTITY_ID)
        self._session = requests.session()
        self._vacuum_state = None
        self._frame_interval = 1
        self._last_path = None
        self._vac_data_size_x = None
        self._vac_data_size_y = None
        self._vac_data_centre = None
        self._vac_data_pix_size = None
        self._vac_wall_pixels = None
        self._vac_flour_pixels = None
        self._vac_json_data = None
        self._vac_json_id = None
        self._base = None
        self._center = None
        self._current = None
        self._currentAngle = None
        self._temp_dir = "config/tmp"
        self._image = self.update()
        self._last_image = None
        self.throttled_camera_image = Throttle(timedelta(seconds=5))(self.camera_image)
        self._should_poll = True
        self.async_camera_image(True)

    async def async_added_to_hass(self) -> None:
        self.async_schedule_update_ha_state(True)

    @property
    def frame_interval(self) -> float:
        return 1

    def camera_image(self, width: Optional[int] = None, height: Optional[int] = None) -> Optional[bytes]:
        if self._image != None:
            self._last_image = self._image
            return self._image
        else:
            return self._last_image

    @property
    def name(self) -> str:
        return self._name

    def turn_on(self):
        self._should_poll = True

    def turn_off(self):
        self._should_poll = False

    """ #@property
    #def supported_features(self) -> int:
    #    return SUPPORT_ON_OFF """

    @property
    def extra_state_attributes(self):
        return {
            "vacuum_entiy": self._vacuum_entity,
            "vacuum_status": self._vacuum_state,
            "vacuum_json_data": self._vac_json_id,
            "Image Centre": self._center,
            "robot_position": self._current,
            "charger_position": self._base,
            "json_data": self._vac_json_data,
        }

    @property
    def should_poll(self) -> bool:
        return self._should_poll

    def update(self):

        def sublist(lst, n):
            sub = []
            result = []
            for ni in lst:
                sub += [ni]
                if len(sub) == n:
                    result += [sub]
                    sub = []
            if sub:
                result += [sub]
            return result

        def sublist_join(lst, n):
            result = []
            sub = [lst[0]]
            for i in range(1, len(lst)):
                sub.append(lst[i])
                if len(sub) == n:
                    result.append(sub)
                    sub = [lst[i]]
            if sub:
                result.append(sub)
            return result

        def find_points_entities(json_obj, entity_dict=None):
            if entity_dict is None:
                entity_dict = {}
            if isinstance(json_obj, dict):
                if '__class' in json_obj and json_obj['__class'] == 'PointMapEntity':
                    entity_type = json_obj.get('type')
                    if entity_type:
                        if entity_type not in entity_dict:
                            entity_dict[entity_type] = []
                        entity_dict[entity_type].append(json_obj)
                for key, value in json_obj.items():
                    find_points_entities(value, entity_dict)
            elif isinstance(json_obj, list):
                for item in json_obj:
                    find_points_entities(item, entity_dict)
            return entity_dict

        def from_json_to_image(data, pixel_size, color):
            # Create an array of zeros for the image
            image_array = np.zeros((5120, 5120, 4), dtype=np.uint8)

            # Draw rectangles for each point in data
            for x, y, z in data:
                for i in range(z):
                    col = (x + i) * pixel_size
                    row = y * pixel_size
                    image_array[row:row + pixel_size, col:col + pixel_size] = color

            # Convert the image array to a PIL image
            return image_array

        def draw_robot(layers, x, y, angle, robot_color):
            radius = 5
            thickness = 30
            cv2.circle(layers, (x, y), radius, robot_color, thickness)

            lidar_angle = math.radians(angle - 90)
            lidar_x = int(x + 9 * math.cos(lidar_angle))
            lidar_y = int(y + 9 * math.sin(lidar_angle))
            cv2.circle(layers, (lidar_x, lidar_y), 1, (255, 204, 153, 255), thickness=5)

        def draw_battery_charger(layers, x, y, color):
            charger_width = 10
            charger_height = 20

            # Get the starting and ending indices of the charger rectangle
            start_row = y - charger_height // 2
            end_row = start_row + charger_height
            start_col = x - charger_width // 2
            end_col = start_col + charger_width

            # Fill in the charger rectangle with the specified color
            layers[start_row:end_row, start_col:end_col] = color

            return layers

        def draw_go_to_flag(center, layer):
            # Define flag color
            flag_color = (0, 255, 0)  # RGB color (green)

            # Define flag size and position
            flag_size = 40
            x1 = center[0] - flag_size // 2
            y1 = center[1] - flag_size // 2
            x2 = center[0] + flag_size // 2
            y2 = center[1] + flag_size // 2

            # Draw flag on layer
            cv2.rectangle(layer, (x1, y1), (x2, y2), flag_color, -1)

            # Draw flag pole
            pole_width = 5
            pole_color = (0, 0, 255, 255)  # RGB color (blue)
            cv2.rectangle(layer, (center[0] - pole_width // 2, y1), (center[0] + pole_width // 2, y2), pole_color, -1)

            return layer

        def draw_lines(arr, coords, width, color):
            for coord in coords:
                # Use Bresenham's line algorithm to get the coordinates of the line pixels
                x0, y0 = coord[0]
                try:
                    x1, y1 = coord[1]
                except:
                    x1 = x0
                    y1 = y0
                dx = abs(x1 - x0)
                dy = abs(y1 - y0)
                sx = 1 if x0 < x1 else -1
                sy = 1 if y0 < y1 else -1
                err = dx - dy
                line_pixels = []
                while True:
                    line_pixels.append((x0, y0))
                    if x0 == x1 and y0 == y1:
                        break
                    e2 = 2 * err
                    if e2 > -dy:
                        err -= dy
                        x0 += sx
                    if e2 < dx:
                        err += dx
                        y0 += sy

                # Iterate over the line pixels and draw filled rectangles with the specified width
                for pixel in line_pixels:
                    x, y = pixel
                    for i in range(width):
                        for j in range(width):
                            if 0 <= x + i < arr.shape[0] and 0 <= y + j < arr.shape[1]:
                                arr[y + i, x + j] = color
            return arr

        try:
            #test purpose only we retrive the json directly from the vacuum rest api
            #the vacuum is connected via MQTT to a different ha instance
            url = 'http://valetudo-silenttepidstinkbug.local/api/v2/robot/state/map'
            headers = {'accept': 'application/json'}
            self._vac_json_data = "Success"
            response = self._session.get(url, headers=headers, timeout=10)

        except Exception:
            self._vac_json_data = "Error"
            pass
        else:
            resp_data = response.content
            parsed_json = json.loads(resp_data.decode('utf-8'))
            # Extract from the Valetudo Jason the relevant data.
            entity_dict = find_points_entities(parsed_json)
            robot_pos = entity_dict.get("robot_position")
            go_to = entity_dict.get("go_to_target")
            self._vac_json_id = parsed_json["metaData"]["nonce"]
            flour_pixels = parsed_json["layers"][0]["compressedPixels"]
            walls_pixels = parsed_json["layers"][1]["compressedPixels"]
            path_pixels = parsed_json["entities"][0]["points"]
            # path_array = np.array(path_pixels)
            charger_pos = parsed_json["entities"][1]["points"]
            if self._vacuum_state == "docked":
                x = charger_pos[0]
                y = charger_pos[1]
                a = parsed_json["entities"][2]["metaData"]["angle"]
                self._base = {"x": x, "y": y, "a": a}

            robot_position = robot_pos[0]["points"]
            robot_position_angle = robot_pos[0]["metaData"]["angle"]
            self._current = {"x": robot_position[0], "y": robot_position[1], "a": robot_position_angle}

            # Calibration data of the result image
            # Size X and Y give the result as calculated in the robot.
            # Pixel size is defined for lidar resolution and image points location.

            size_x = int(parsed_json["size"]["x"])
            size_y = int(parsed_json["size"]["y"])
            pixel_size = int(parsed_json["pixelSize"])
            self._vac_data_size_x = size_x
            self._vac_data_size_y = size_y
            self._vac_data_centre = {"x": size_x // 2, "y": size_y // 2}

            # Initialize Pixels arrays
            flour_pixel = sublist(flour_pixels, 3)
            wall_pixel = sublist(walls_pixels, 3)
            path_pixel = sublist(path_pixels, 2)
            self._last_path = path_pixel
            path_pixel2 = sublist_join(path_pixel, 2)

            # Colours defined
            charger_color = (0, 128, 0, 255)
            color_move = (238, 247, 255, 255)  # (192, 192, 192, 255)
            color_ext_background = (125, 125, 125, 255)
            color_robot = (255, 255, 204, 255)
            color_home_background = (0, 255, 255, 255)
            color_wall = (255, 255, 0, 255)
            color_white = (255, 255, 255, 255)
            color_grey = (125, 125, 125, 255)
            color_black = (0, 0, 0, 255)
            color_transparent = (0, 0, 0, 0)

            # Numpy array pixels positions and colours computation
            img_np_array = from_json_to_image(flour_pixel, pixel_size, color_home_background)
            img_np_array = img_np_array + from_json_to_image(wall_pixel, pixel_size, color_wall)
            img_np_array = draw_lines(img_np_array, path_pixel2, 5, color_move)
            img_np_array = draw_battery_charger(img_np_array, charger_pos[0], charger_pos[1], charger_color)
            if go_to:
                draw_go_to_flag((go_to[0]["points"][0], go_to[0]["points"][1]), img_np_array)
            draw_robot(img_np_array, robot_position[0], robot_position[1], robot_position_angle, color_robot)

            # Preparing the camera image with openCV from Numpy array
            img = cv2.cvtColor(img_np_array, cv2.COLOR_RGBA2BGRA)
            # Encode the image as a JPEG
            _, data = cv2.imencode(".png", img)
            # Get the bytes object
            bytes_data = data.tobytes()
            self._image = bytes_data

            return bytes_data
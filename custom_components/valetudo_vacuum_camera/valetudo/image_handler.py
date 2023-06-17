
import logging

import numpy as np
import math
from PIL import Image, ImageDraw

_LOGGER = logging.getLogger(__name__)


from custom_components.valetudo_vacuum_camera.utils.colors import (
    color_charger,
    color_move,
    color_wall,
    color_robot,
    color_home_background,
    color_grey,
)

class MapImageHandler(object):
    def __init__(self):
        self.img_size = None
        self.crop_area = None
        self.crop_img_size = None
        self.img_base_layer = None
        self.prev_base_layer = None
        self.path_pixels = None
        self.robot_pos = None
        self.charger_pos = None
        self.json_id = None
        self.go_to = None

    @staticmethod
    def sublist(lst, n):
        return [lst[i:i+n] for i in range(0, len(lst), n)]

    @staticmethod
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

    @staticmethod
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
                MapImageHandler.find_points_entities(value, entity_dict)
        elif isinstance(json_obj, list):
            for item in json_obj:
                MapImageHandler.find_points_entities(item, entity_dict)
        return entity_dict

    @staticmethod
    def find_paths_entities(json_obj, entity_dict=None):
        if entity_dict is None:
            entity_dict = {}
        if isinstance(json_obj, dict):
            if '__class' in json_obj and json_obj['__class'] == 'PathMapEntity':
                entity_type = json_obj.get('type')
                if entity_type:
                    if entity_type not in entity_dict:
                        entity_dict[entity_type] = []
                    entity_dict[entity_type].append(json_obj)
            for key, value in json_obj.items():
                MapImageHandler.find_paths_entities(value, entity_dict)
        elif isinstance(json_obj, list):
            for item in json_obj:
                MapImageHandler.find_paths_entities(item, entity_dict)
        return entity_dict

    @staticmethod
    def find_zone_entities(json_obj, entity_dict=None):
        if entity_dict is None:
            entity_dict = {}
        if isinstance(json_obj, dict):
            if '__class' in json_obj and json_obj['__class'] == 'PolygonMapEntity':
                entity_type = json_obj.get('type')
                if entity_type:
                    if entity_type not in entity_dict:
                        entity_dict[entity_type] = []
                    entity_dict[entity_type].append(json_obj)
            for key, value in json_obj.items():
                MapImageHandler.find_zone_entities(value, entity_dict)
        elif isinstance(json_obj, list):
            for item in json_obj:
                MapImageHandler.find_zone_entities(item, entity_dict)
        return entity_dict

    @staticmethod
    def from_json_to_image( data, pixel_size, color):
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

    def crop_array(self, image_array, crop_percentage):
        """Crops a numpy array and returns the cropped image and scale factor."""
        center_x = image_array.shape[1] // 2
        center_y = image_array.shape[0] // 2
        crop_size = int(min(center_x, center_y) * crop_percentage / 100)
        cropbox = (center_x - crop_size, center_y - crop_size, center_x + crop_size, center_y + crop_size)
        self.crop_area =cropbox
        _LOGGER.debug("Crop Box data: %s", self.crop_area)
        cropped = image_array[cropbox[1]:cropbox[3], cropbox[0]:cropbox[2]]
        self.crop_img_size = (cropped.shape[1], cropped.shape[0])
        _LOGGER.debug("Crop image size: %s", self.crop_img_size)
        return cropped

    @staticmethod
    def draw_robot(layers, x, y, angle, fill):
        tmpimg = Image.fromarray(np.zeros_like(layers))
        draw = ImageDraw.Draw(tmpimg)
        outline = (
            (fill[0]) // 2,
            (fill[1]) // 2,
            (fill[2]) // 2
        )
        radius = 25
        r_scaled = radius // 11
        #draw the robot outline
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill, outline=outline)
        #draw bin cover
        r_cover = r_scaled * 12
        angle = angle - 80
        lidar_angle = np.deg2rad(angle+170)  # Convert angle to radians and adjust for LIDAR orientation
        a1 = (((angle+80) - 104) / 180 * math.pi)
        a2 = (((angle+80) + 104) / 180 * math.pi)
        x1 = int(x - r_cover * math.sin(a1))
        y1 = int(y + r_cover * math.cos(a1))
        x2 = int(x - r_cover * math.sin(a2))
        y2 = int(y + r_cover * math.cos(a2))
        draw.line((x1, y1, x2, y2), fill=outline, width=1)
        #Draw Lidar
        lidar_x = int(x + 15 * np.cos(lidar_angle))  # Calculate LIDAR endpoint x-coordinate
        lidar_y = int(y + 15 * np.sin(lidar_angle))  # Calculate LIDAR endpoint y-coordinate
        r_lidar = r_scaled * 3
        draw.ellipse((lidar_x - r_lidar, lidar_y - r_lidar, lidar_x + r_lidar, lidar_y + r_lidar), fill=outline, width=5)
        # Convert the PIL image back to a Numpy array
        return np.array(tmpimg)

    @staticmethod
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

    @staticmethod
    def draw_go_to_flag(center, layer):
        # Define flag color
        flag_color = (0, 255, 0)  # RGB color (green)
        # Define flag size and position
        flag_size = 40
        x1 = center[0] - flag_size // 2
        y1 = center[1] - flag_size // 2
        x2 = center[0] + flag_size // 2
        y2 = center[1] + flag_size // 2
        # Create an Image object from the layer array
        tmp_img = Image.fromarray(layer)

        # Draw flag on layer
        draw = ImageDraw.Draw(tmp_img)
        draw.rectangle((x1, y1, x2, y2), fill=flag_color)
        # Draw flag pole
        pole_width = 5
        pole_color = (0, 0, 255, 255)  # RGB color (blue)
        draw.rectangle((center[0] - pole_width // 2, y1, center[0] + pole_width // 2, y2), fill=pole_color)
        # Convert the Image object back to the numpy array
        layer = np.array(tmp_img)
        return layer

    #Draw cleaning selected area
    @staticmethod
    def draw_rectangle(coordinates, layer, color):
        # Create an Image object from the numpy array
        tmp_img = Image.fromarray(layer)

        # Draw rectangle on the image
        draw = ImageDraw.Draw(tmp_img)
        draw.polygon(coordinates, fill=color, outline=color_grey, width=1)

        # Convert the Image object back to the numpy array
        out_layer = np.array(tmp_img)

        return out_layer

    # Draw line within given coordinates x,y and add it to the array in input
    @staticmethod
    def draw_lines(arr, coords, width, color):
        for coord in coords:
            # Use Bresenham's line algorithm to get the coordinates of the line pixels
            x0, y0 = coord[0]
            try:
                x1, y1 = coord[1]
            except IndexError:
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

    def get_image_from_json(self, m_json):

        if m_json is not None:
            # Reading and splitting the Json form Valetudo
            size_x = int(m_json["size"]["x"])
            size_y = int(m_json["size"]["y"])
            self.img_size = {
                "x": size_x,
                "y": size_y,
                "centre": [(size_x // 2), (size_y // 2)]
            }

            self.json_id = m_json["metaData"]["nonce"]

            #Predicted path if any
            predicted_pat2 = None
            predicted_path = self.find_paths_entities(m_json, None)
            predicted_path = predicted_path.get("predicted_path")
            if predicted_path:
                predicted_path = predicted_path[0]["points"]
                predicted_path = self.sublist(predicted_path, 2)
                predicted_pat2 = self.sublist_join(predicted_path, 2)

            #Zone cleaning area if any
            zone_clean = self.find_zone_entities(m_json, None)

            #Saerching the "points" robot, charger and go_to
            entity_dict = self.find_points_entities(m_json, None)
            robot_pos = entity_dict.get("robot_position")
            robot_position = robot_pos[0]["points"]
            robot_position_angle = robot_pos[0]["metaData"]["angle"]
            self.robot_pos = {
                "x": robot_position[0],
                "y": robot_position[1],
                "angle": robot_position_angle
            }
            charger_pos = entity_dict.get("charger_location")
            if charger_pos:
                charger_pos = charger_pos[0]["points"]
                self.charger_pos = {
                    "x": charger_pos[0],
                    "y": charger_pos[1],
                }
            go_to = entity_dict.get("go_to_target")

            """Calibration data of the result image
            Size X and Y give the result as calculated in the robot.
            Pixel size is defined for lidar resolution and image points location. """

            pixel_size = int(m_json["pixelSize"])
            flour_pixels = m_json["layers"][0]["compressedPixels"]
            walls_pixels = m_json["layers"][1]["compressedPixels"]
            path_pixels = m_json["entities"][0]["points"]

            # Formatting the data arrays for Numpy
            flour_pixels = self.sublist(flour_pixels, 3)
            walls_pixels = self.sublist(walls_pixels, 3)
            path_pixels = self.sublist(path_pixels, 2)
            path_pixel2 = self.sublist_join(path_pixels, 2)

            # Numpy array pixels positions and colours computation
            img_np_array = self.from_json_to_image(flour_pixels, pixel_size, color_home_background)
            if zone_clean:
                zones_clean = zone_clean.get("active_zone")
                tot_zones = len(zones_clean)-1
                while tot_zones >= 0:
                    tot_zones = tot_zones -1
                    img_np_array = self.draw_rectangle((zones_clean[tot_zones]["points"]),
                                                       img_np_array, (0, 255, 0, 16))
            img_np_array = img_np_array + self.from_json_to_image(walls_pixels, pixel_size, color_wall)
            if charger_pos:
                img_np_array = self.draw_battery_charger(img_np_array,
                                                         charger_pos[0],
                                                         charger_pos[1],
                                                         color_charger)
            #self.img_base_layer = img_np_array # Store flour, walls and charger combined NP array.
            if go_to: # if we have a goto position draw the flag end point.
                img_np_array = self.draw_go_to_flag((go_to[0]["points"][0],
                                                     go_to[0]["points"][1]),
                                                    img_np_array)
            # finally let´s add the robot layer
            if predicted_pat2:
                img_np_array = self.draw_lines(img_np_array, predicted_pat2, 2, color_grey)
            img_np_array = self.draw_lines(img_np_array, path_pixel2, 5, color_move)
            img_np_array = img_np_array + self.draw_robot(img_np_array,
                                                          robot_position[0],
                                                          robot_position[1],
                                                          robot_position_angle,
                                                          color_robot)
            # The image is cropped 75% so that the last layer is smaller to be sent.
            img_np_array = self.crop_array(img_np_array, 25)
            # Conversion of NP array to PIL image
            pil_img = Image.fromarray(img_np_array, mode="RGBA")
            return pil_img
        else:
            return None

    def get_robot_position(self):
        return self.robot_pos

    def get_charger_position(self):
        return self.charger_pos

    def get_img_size(self):
        return self.img_size

    def get_json_id(self):
        return self.json_id

    def get_calibration_data(self):
        calibration_data = []

        # Calculate the calibration points in the vacuum coordinate system
        vacuum_points = [
            {"x": self.crop_area[0], "y": self.crop_area[1]},  # Top-left corner
            {"x": self.crop_area[2], "y": self.crop_area[1]},  # Top-right corner
            {"x": self.crop_area[2], "y": self.crop_area[3]},  # Bottom-right corner
            {"x": self.crop_area[0], "y": self.crop_area[3]}   # Bottom-left corner (optional)
        ]

        # Calculate the corresponding map coordinates based on the crop image size
        map_points = [
            {"x": 0, "y": 0},                              # Top-left corner
            {"x": self.crop_img_size[0], "y": 0},           # Top-right corner
            {"x": self.crop_img_size[0], "y": self.crop_img_size[1]},  # Bottom-right corner
            {"x": 0, "y": self.crop_img_size[1]}            # Bottom-left corner (optional)
        ]

        # Create the calibration data for each point
        for vacuum_point, map_point in zip(vacuum_points, map_points):
            calibration_point = {
                "vacuum": vacuum_point,
                "map": map_point
            }
            calibration_data.append(calibration_point)

        return calibration_data

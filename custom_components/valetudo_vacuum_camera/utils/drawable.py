"""
Collections of Drawing Utility
Drawable is part of the Image_Handler
used functions to draw the elements on the Numpy Array
that is actually our camera frame.
Version: v2024.06.1
"""

from __future__ import annotations

import math

from PIL import ImageDraw, ImageFont
import numpy as np

from custom_components.valetudo_vacuum_camera.types import (
    Color,
    NumpyArray,
    PilPNG,
    Point,
)

# import re


class Drawable:
    """
    Collection of drawing utility functions for the image handlers.
    This class contains static methods to draw various elements on the Numpy Arrays (images).
    We cant use openCV because it is not supported by the Home Assistant OS.
    """

    @staticmethod
    async def create_empty_image(
        width: int, height: int, background_color: Color
    ) -> NumpyArray:
        """Create the empty background image numpy array."""
        """ Background color is specified as RGBA tuple. """
        image_array = np.full((height, width, 4), background_color, dtype=np.uint8)
        return image_array

    @staticmethod
    async def from_json_to_image(
        layer: NumpyArray, pixels: dict, pixel_size: int, color: Color
    ) -> NumpyArray:
        """Drawing the layers (rooms) from the vacuum json data."""
        image_array = layer
        # Loop through pixels to find min and max coordinates
        for x, y, z in pixels:
            col = x * pixel_size
            row = y * pixel_size
            # Draw pixels
            for i in range(z):
                image_array[
                    row : row + pixel_size,
                    col + i * pixel_size : col + (i + 1) * pixel_size,
                ] = color
        return image_array

    @staticmethod
    async def battery_charger(
        layers: NumpyArray, x: int, y: int, color: Color
    ) -> NumpyArray:
        """Draw the battery charger on the input layer."""
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
    async def go_to_flag(
        layer: NumpyArray, center: Point, rotation_angle: int, flag_color: Color
    ) -> NumpyArray:
        """
        It is draw a flag on centered at specified coordinates on
        the input layer. It uses the rotation angle of the image
        to orientate the flag on the given layer.
        """
        # Define flag color
        pole_color = (0, 0, 255, 255)  # RGBA color (blue)
        # Define flag size and position
        flag_size = 50
        pole_width = 6
        # Adjust flag coordinates based on rotation angle
        if rotation_angle == 90:
            x1 = center[0] + flag_size
            y1 = center[1] - (pole_width // 2)
            x2 = x1 - (flag_size // 4)
            y2 = y1 + (flag_size // 2)
            x3 = center[0] + (flag_size // 2)
            y3 = center[1] - (pole_width // 2)
            # Define pole end position
            xp1 = center[0]
            yp1 = center[1] - (pole_width // 2)
            xp2 = center[0] + flag_size
            yp2 = center[1] - (pole_width // 2)
        elif rotation_angle == 180:
            x1 = center[0]
            y1 = center[1] - (flag_size // 2)
            x2 = center[0] - (flag_size // 2)
            y2 = y1 + (flag_size // 4)
            x3 = center[0]
            y3 = center[1]
            # Define pole end position
            xp1 = center[0] + (pole_width // 2)
            yp1 = center[1] - flag_size
            xp2 = center[0] + (pole_width // 2)
            yp2 = y3
        elif rotation_angle == 270:
            x1 = center[0] - flag_size
            y1 = center[1] + (pole_width // 2)
            x2 = x1 + (flag_size // 4)
            y2 = y1 - (flag_size // 2)
            x3 = center[0] - (flag_size // 2)
            y3 = center[1] + (pole_width // 2)
            # Define pole end position
            xp1 = center[0] - flag_size
            yp1 = center[1] + (pole_width // 2)
            xp2 = center[0]
            yp2 = center[1] + (pole_width // 2)
        else:
            # rotation_angle == 0 (no rotation)
            x1 = center[0]
            y1 = center[1]
            x2 = center[0] + (flag_size // 2)
            y2 = y1 + (flag_size // 4)
            x3 = center[0]
            y3 = center[1] + flag_size // 2
            # Define pole end position
            xp1 = center[0] - (pole_width // 2)
            yp1 = y1
            xp2 = center[0] - (pole_width // 2)
            yp2 = center[1] + flag_size

        # Draw flag outline using _polygon_outline
        points = [(x1, y1), (x2, y2), (x3, y3)]
        layer = Drawable._polygon_outline(layer, points, 1, flag_color, flag_color)

        # Draw pole using _line
        layer = Drawable._line(layer, xp1, yp1, xp2, yp2, pole_color, pole_width)

        return layer

    @staticmethod
    def point_inside(x: int, y: int, points) -> bool:
        """
        Check if a point (x, y) is inside a polygon defined by a list of points.
        Utility to establish the fill point of the geometry.
        Parameters:
        - x, y: Coordinates of the point to check.
        - points: List of (x, y) coordinates defining the polygon.

        Returns:
        - True if the point is inside the polygon, False otherwise.
        """
        n = len(points)
        inside = False
        xinters = 0
        p1x, p1y = points[0]
        for i in range(1, n + 1):
            p2x, p2y = points[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y

        return inside

    @staticmethod
    def _line(
        layer: NumpyArray,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        color: Color,
        width: int = 3,
    ) -> NumpyArray:
        """
        Draw a line on a NumPy array (layer) from point A to B.
        Parameters:
        - layer: NumPy array representing the image.
        - x1, y1: Starting coordinates of the line.
        - x2, y2: Ending coordinates of the line.
        - color: Color of the line (e.g., [R, G, B] or [R, G, B, A] for RGBA).
        - width: Width of the line (default is 3).

        Returns:
        - Modified layer with the line drawn.
        """
        # Ensure the coordinates are integers
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

        # Use Bresenham's line algorithm to get the coordinates of the line pixels
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy

        while True:
            # Draw a rectangle with the specified width at the current coordinates
            for i in range(-width // 2, (width + 1) // 2):
                for j in range(-width // 2, (width + 1) // 2):
                    if 0 <= x1 + i < layer.shape[1] and 0 <= y1 + j < layer.shape[0]:
                        layer[y1 + j, x1 + i] = color

            if x1 == x2 and y1 == y2:
                break

            e2 = 2 * err

            if e2 > -dy:
                err -= dy
                x1 += sx

            if e2 < dx:
                err += dx
                y1 += sy

        return layer

    @staticmethod
    async def draw_virtual_walls(
        layer: NumpyArray, virtual_walls, color: Color
    ) -> NumpyArray:
        """
        Draw virtual walls on the input layer.
        """
        for wall in virtual_walls:
            for i in range(0, len(wall), 4):
                x1, y1, x2, y2 = wall[i : i + 4]
                # Draw the virtual wall as a line with a fixed width of 6 pixels
                layer = Drawable._line(layer, x1, y1, x2, y2, color, width=6)
        return layer

    @staticmethod
    async def lines(arr: NumpyArray, coords, width: int, color: Color) -> NumpyArray:
        """
        it joins the coordinates creating a continues line.
        the result is our path.
        """
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

    @staticmethod
    def _filled_circle(
        image: NumpyArray,
        center: Point,
        radius: int,
        color: Color,
        outline_color: Color = None,
        outline_width: int = 0,
    ) -> NumpyArray:
        """
        Draw a filled circle on the image using NumPy.

        Parameters:
        - image: NumPy array representing the image.
        - center: Center coordinates of the circle (x, y).
        - radius: Radius of the circle.
        - color: Color of the circle (e.g., [R, G, B] or [R, G, B, A] for RGBA).

        Returns:
        - Modified image with the filled circle drawn.
        """
        y, x = center
        rr, cc = np.ogrid[: image.shape[0], : image.shape[1]]
        circle = (rr - x) ** 2 + (cc - y) ** 2 <= radius**2
        image[circle] = color
        if outline_width > 0:
            # Create a mask for the outer circle
            outer_circle = (rr - x) ** 2 + (cc - y) ** 2 <= (
                radius + outline_width
            ) ** 2
            # Create a mask for the outline by subtracting the inner circle mask from the outer circle mask
            outline_mask = outer_circle & ~circle
            # Fill the outline with the outline color
            image[outline_mask] = outline_color

        return image

    @staticmethod
    def _ellipse(
        image: NumpyArray, center: Point, radius: int, color: Color
    ) -> NumpyArray:
        """
        Draw an ellipse on the image using NumPy.
        """
        # Create a copy of the image to avoid modifying the original
        result_image = image
        # Calculate the coordinates of the ellipse's bounding box
        x, y = center
        x1, y1 = x - radius, y - radius
        x2, y2 = x + radius, y + radius
        # Draw the filled ellipse
        result_image[y1:y2, x1:x2] = color
        return result_image

    @staticmethod
    def _polygon_outline(
        arr: NumpyArray,
        points,
        width: int,
        outline_color: Color,
        fill_color: Color = None,
    ) -> NumpyArray:
        """
        Draw the outline of a filled polygon on the array using _line.
        """
        for i in range(len(points)):
            # Get the current and next points to draw a line between them
            current_point = points[i]
            next_point = points[(i + 1) % len(points)]  # Wrap around to the first point
            # Use the _line function to draw a line between the current and next points
            arr = Drawable._line(
                arr,
                current_point[0],
                current_point[1],
                next_point[0],
                next_point[1],
                outline_color,
                width,
            )
            # Fill the polygon area with the specified fill color
            if fill_color is not None:
                min_x = min(point[0] for point in points)
                max_x = max(point[0] for point in points)
                min_y = min(point[1] for point in points)
                max_y = max(point[1] for point in points)
                # check if we are inside the area and set the color
                for x in range(min_x, max_x + 1):
                    for y in range(min_y, max_y + 1):
                        if Drawable.point_inside(x, y, points):
                            arr[y, x] = fill_color
        return arr

    @staticmethod
    async def zones(layers: NumpyArray, coordinates, color: Color) -> NumpyArray:
        """
        Draw the zones on the input layer.
        """
        dot_radius = 1  # number of pixels the dot should be
        dot_spacing = 4  # space between dots.
        # Iterate over zones
        for zone in coordinates:
            points = zone["points"]
            # determinate the points to cover.
            min_x = min(points[::2])
            max_x = max(points[::2])
            min_y = min(points[1::2])
            max_y = max(points[1::2])
            # Draw ellipses (dots)
            for y in range(min_y, max_y, dot_spacing):
                for x in range(min_x, max_x, dot_spacing):
                    for i in range(dot_radius):
                        layers = Drawable._ellipse(layers, (x, y), dot_radius, color)
        return layers

    @staticmethod
    async def robot(
        layers: NumpyArray, x: int, y: int, angle: float, fill: Color, log: str = ""
    ) -> NumpyArray:
        """
        We Draw the robot with in a smaller array
        this helps numpy to work faster and at lower
        memory cost.
        """
        # Create a 52*52 empty image numpy array of the background
        top_left_x = x - 26
        top_left_y = y - 26
        bottom_right_x = top_left_x + 52
        bottom_right_y = top_left_y + 52
        tmp_layer = layers[top_left_y:bottom_right_y, top_left_x:bottom_right_x].copy()
        # centre of the above array is used from the rest of the code.
        # to draw the robot.
        tmp_x, tmp_y = 26, 26
        # Draw Robot
        radius = 25  # Radius of the vacuum constant
        r_scaled = radius // 11  # Offset scale for placement of the objects.
        r_cover = r_scaled * 12  # Scale factor for cover
        lidar_angle = np.deg2rad(
            angle + 90
        )  # Convert angle to radians and adjust for LIDAR orientation
        r_lidar = r_scaled * 3  # Scale factor for the lidar
        r_button = r_scaled * 1  # scale factor of the button
        # Outline colour from fill colour
        outline = (fill[0] // 2, fill[1] // 2, fill[2] // 2, fill[3])
        # Draw the robot outline
        tmp_layer = Drawable._filled_circle(
            tmp_layer, (tmp_x, tmp_y), radius, fill, outline, 1
        )
        # Draw bin cover
        angle -= 90  # we remove 90 for the cover orientation
        a1 = ((angle + 90) - 80) / 180 * math.pi
        a2 = ((angle + 90) + 80) / 180 * math.pi
        x1 = int(tmp_x - r_cover * math.sin(a1))
        y1 = int(tmp_y + r_cover * math.cos(a1))
        x2 = int(tmp_x - r_cover * math.sin(a2))
        y2 = int(tmp_y + r_cover * math.cos(a2))
        tmp_layer = Drawable._line(tmp_layer, x1, y1, x2, y2, outline, width=1)
        # Draw Lidar
        lidar_x = int(tmp_x + 15 * np.cos(lidar_angle))  # Calculate LIDAR x-coordinate
        lidar_y = int(tmp_y + 15 * np.sin(lidar_angle))  # Calculate LIDAR y-coordinate
        tmp_layer = Drawable._filled_circle(
            tmp_layer, (lidar_x, lidar_y), r_lidar, outline
        )
        # Draw Button
        butt_x = int(
            tmp_x - 20 * np.cos(lidar_angle)
        )  # Calculate the button x-coordinate
        butt_y = int(
            tmp_y - 20 * np.sin(lidar_angle)
        )  # Calculate the button y-coordinate
        tmp_layer = Drawable._filled_circle(
            tmp_layer, (butt_x, butt_y), r_button, outline
        )
        # at last overlay the new robot image to the layer in input.
        layers = Drawable.overlay_robot(layers, tmp_layer, x, y)
        # return the new layer as np array.
        return layers

    @staticmethod
    def overlay_robot(
        background_image: NumpyArray, robot_image: NumpyArray, x: int, y: int
    ) -> NumpyArray:
        """
        Overlay the robot image on the background image at the specified coordinates.
        @param background_image:
        @param robot_image:
        @param robot x:
        @param robot y:
        @return: robot image overlaid on the background image.
        """
        # Calculate the dimensions of the robot image
        robot_height, robot_width, _ = robot_image.shape
        # Calculate the center of the robot image (in case const changes)
        robot_center_x = robot_width // 2
        robot_center_y = robot_height // 2
        # Calculate the position to overlay the robot on the background image
        top_left_x = x - robot_center_x
        top_left_y = y - robot_center_y
        bottom_right_x = top_left_x + robot_width
        bottom_right_y = top_left_y + robot_height
        # Overlay the robot on the background image
        background_image[top_left_y:bottom_right_y, top_left_x:bottom_right_x] = (
            robot_image
        )
        return background_image

    @staticmethod
    def draw_obstacles(
        image: NumpyArray, obstacle_info_list, color: Color
    ) -> NumpyArray:
        """
        Draw filled circles for obstacles on the image.
        Parameters:
        - image: NumPy array representing the image.
        - obstacle_info_list: List of dictionaries containing obstacle information.
        Returns:
        - Modified image with filled circles for obstacles.
        """
        for obstacle_info in obstacle_info_list:
            enter = obstacle_info.get("points", {})
            # label = obstacle_info.get("label", {})
            center = (enter["x"], enter["y"])

            radius = 6

            # Draw filled circle
            image = Drawable._filled_circle(image, center, radius, color)

        return image

    @staticmethod
    def status_text(
        image: PilPNG,
        size: int,
        color: Color,
        status: list[str],
        path_font: str,
        position: bool,
    ) -> None:
        """Draw the Status Test on the image."""
        # Load a fonts
        path_default_font = (
            "custom_components/valetudo_vacuum_camera/utils/fonts/FiraSans.ttf"
        )
        default_font = ImageFont.truetype(path_default_font, size)
        user_font = ImageFont.truetype(path_font, size)
        # Define the text and position
        if position:
            x, y = 10, 10
        else:
            x, y = 10, image.height - 20 - size
        # Create a drawing object
        draw = ImageDraw.Draw(image)
        # Draw the text
        for text in status:
            if "\u2211" in text or "\u03DE" in text:
                font = default_font
                width = None
            else:
                font = user_font
                is_variable = path_font.endswith("VT.ttf")
                if is_variable:
                    width = 2
                else:
                    width = None
            if width:
                draw.text((x, y), text, font=font, fill=color, stroke_width=width)
            else:
                draw.text((x, y), text, font=font, fill=color)
            x += draw.textlength(text, font=default_font)

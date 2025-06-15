"""
Obstacle View Handler Module
Version: 2025.6.0
This module handles obstacle view functionality for the MQTT Vacuum Camera.
Extracted from camera.py to improve modularity and maintainability.
"""

from __future__ import annotations

import asyncio
import math
import time
from typing import Any, Optional

from homeassistant.exceptions import HomeAssistantError
from valetudo_map_parser.config.utils import ResizeParams, async_resize_image

from ...const import DOWNLOAD_TIMEOUT, LOGGER, CameraModes


class ObstacleViewHandler:
    """
    Handles obstacle view functionality for the MQTT Vacuum Camera.
    This class encapsulates all obstacle-related operations to keep the main camera class clean.
    """

    def __init__(
        self,
        shared_data: Any,
        file_name: str,
        processor: Any,
        hass: Any,
        entity_id: str,
        thread_pool: Any,
    ):
        """
        Initialize the ObstacleViewHandler.
        
        Args:
            shared_data: Camera shared data object
            file_name: Vacuum file name for logging
            processor: CameraProcessor instance
            hass: Home Assistant instance
            entity_id: Camera entity ID
            thread_pool: Thread pool manager
        """
        self._shared = shared_data
        self._file_name = file_name
        self.processor = processor
        self.hass = hass
        self.entity_id = entity_id
        self.thread_pool = thread_pool

    async def handle_obstacle_view(self, event_data: dict, camera_instance: Any) -> Optional[bytes]:
        """
        Handle the obstacle view event.

        Args:
            event_data: The obstacle view event
            camera_instance: The camera instance to work with

        Returns:
            The processed image bytes or None
        """
        width = self._shared.image_ref_width
        height = self._shared.image_ref_height
        shared_ratio = self._shared.image_aspect_ratio
        obstacles_data = self._shared.obstacles_data

        async def _set_map_view_mode(reason: str = None) -> Optional[bytes]:
            """Set the camera mode to MAP_VIEW."""
            self._shared.camera_mode = CameraModes.MAP_VIEW
            LOGGER.debug(
                "%s: Camera Mode Change to %s%s",
                self._file_name,
                self._shared.camera_mode,
                f", {reason}" if reason else "",
            )
            if camera_instance._image_bk:
                LOGGER.debug("%s: Restoring the backup image.", self._file_name)
                camera_instance.Image = camera_instance._image_bk
                return camera_instance.camera_image(camera_instance._image_w, camera_instance._image_h)
            return camera_instance.Image

        async def _set_camera_mode(mode_of_camera: CameraModes, reason: str = None) -> None:
            """Set the camera mode."""
            self._shared.camera_mode = mode_of_camera

            match mode_of_camera:
                case CameraModes.OBSTACLE_SEARCH:
                    if not camera_instance._image_bk:
                        camera_instance._image_bk = camera_instance.Image

                case CameraModes.OBSTACLE_VIEW:
                    self._shared.image_grab = False
                    camera_instance._processing = True

                case CameraModes.MAP_VIEW:
                    camera_instance._obstacle_image = None
                    camera_instance._processing = False
                    self._shared.image_grab = True
                    if camera_instance._image_bk:
                        camera_instance.Image = camera_instance._image_bk
                        camera_instance._image_bk = None
                        camera_instance.camera_image(camera_instance._image_w, camera_instance._image_h)

            LOGGER.debug(
                "%s: Camera Mode Change to %s%s",
                self._file_name,
                self._shared.camera_mode,
                f", {reason}" if reason else "",
            )

        async def _async_find_nearest_obstacle(x: int, y: int, all_obstacles: list) -> Optional[dict]:
            """Find the nearest obstacle to the given coordinates."""
            nearest_obstacles = None
            w = width
            h = height
            min_distance = round(65 * (w / h))
            LOGGER.debug(
                "Finding in the nearest %d pixels obstacle to coordinates: %d, %d",
                min_distance,
                x,
                y,
            )

            for obstacle in all_obstacles:
                obstacle_point = obstacle["point"]
                obstacle_x = obstacle_point["x"]
                obstacle_y = obstacle_point["y"]

                # Calculate Euclidean distance
                distance = math.sqrt((x - obstacle_x) ** 2 + (y - obstacle_y) ** 2)

                if distance < min_distance:
                    min_distance = distance
                    nearest_obstacles = obstacle

            return nearest_obstacles

        LOGGER.debug(
            "%s: Executing obstacle view logic for, Data: %s",
            self._file_name,
            str(event_data),
        )
        
        LOGGER.debug(
            "%s: Current camera mode: %s",
            self._file_name,
            self._shared.camera_mode,
        )

        # Check if we are in obstacle view and switch back to map view
        if self._shared.camera_mode == CameraModes.OBSTACLE_VIEW:
            return await _set_map_view_mode("Obstacle View Exit Requested.")

        # Prevent processing if already in obstacle processing modes
        if self._shared.camera_mode in [CameraModes.OBSTACLE_DOWNLOAD, CameraModes.OBSTACLE_SEARCH]:
            LOGGER.debug(
                "%s: Already processing obstacle view (mode: %s), ignoring request",
                self._file_name,
                self._shared.camera_mode,
            )
            return camera_instance.Image

        if obstacles_data and self._shared.camera_mode == CameraModes.MAP_VIEW:
            event_entity_id = event_data.get("entity_id")
            LOGGER.debug(
                "%s: Entity ID comparison - Event: '%s' vs Camera: '%s'",
                self._file_name,
                event_entity_id,
                self.entity_id,
            )

            await _set_camera_mode(CameraModes.OBSTACLE_SEARCH, "Obstacle View Requested")
            coordinates = event_data.get("coordinates")

            if coordinates:
                obstacles = obstacles_data
                coordinates_x = coordinates.get("x")
                coordinates_y = coordinates.get("y")

                # Find the nearest obstacle
                nearest_obstacle = await _async_find_nearest_obstacle(
                    coordinates_x, coordinates_y, obstacles
                )

                if nearest_obstacle:
                    LOGGER.debug(
                        "%s: Nearest obstacle found: %r",
                        self._file_name,
                        nearest_obstacle,
                    )

                    if not nearest_obstacle["link"]:
                        return await _set_map_view_mode("No link found for the obstacle image.")

                    await _set_camera_mode(
                        mode_of_camera=CameraModes.OBSTACLE_DOWNLOAD,
                        reason=f"Downloading image: {nearest_obstacle['link']}",
                    )

                    # Download and process the image
                    success = await self._download_and_process_obstacle_image(
                        nearest_obstacle, width, height, shared_ratio, camera_instance
                    )

                    if success:
                        await _set_camera_mode(CameraModes.OBSTACLE_VIEW, "Image downloaded successfully")
                        return camera_instance._obstacle_image
                    else:
                        return await _set_map_view_mode("No image downloaded.")

                return await _set_map_view_mode("No nearby obstacle found.")

            return await _set_map_view_mode("No coordinates provided.")
        else:
            return await _set_map_view_mode("No obstacles data available.")

    async def _download_and_process_obstacle_image(
        self,
        nearest_obstacle: dict,
        width: int,
        height: int,
        shared_ratio: str,
        camera_instance: Any,
    ) -> bool:
        """Download and process the obstacle image."""
        try:
            image_data = await asyncio.wait_for(
                fut=self.processor.download_image(nearest_obstacle["link"], DOWNLOAD_TIMEOUT),
                timeout=(DOWNLOAD_TIMEOUT + 1),  # dead man switch, do not remove.
            )
        except asyncio.TimeoutError:
            LOGGER.warning("%s: Image download timed out.", self._file_name)
            return False

        # Process the image if download was successful
        if image_data is not None:
            try:
                start_time = time.perf_counter()
                # Open the downloaded image with PIL
                pil_img = await self.hass.async_create_task(
                    self.processor.async_open_image(image_data)
                )

                # Resize the image if resize_to is provided
                if shared_ratio != "None":
                    resize_data = ResizeParams(
                        pil_img=pil_img,
                        width=width,
                        height=height,
                        aspect_ratio=shared_ratio,
                        crop_size=[],
                        is_rand=False,
                        offset_func=None,
                    )
                    # Handle the case where async_resize_image returns an Image object instead of a tuple
                    resize_result = await async_resize_image(params=resize_data)
                    if isinstance(resize_result, tuple):
                        resized_image, _ = resize_result
                    else:
                        # If it's not a tuple, assume it's the image directly
                        resized_image = resize_result

                    # Use the resized image
                    image = resized_image
                else:
                    # Use original image if no aspect ratio is set
                    image = pil_img

                camera_instance._obstacle_image = await camera_instance.run_async_pil_to_bytes(
                    image, image_id=nearest_obstacle["label"]
                )
                end_time = time.perf_counter()

                LOGGER.debug(
                    "%s: Image processing time: %r seconds",
                    self._file_name,
                    end_time - start_time,
                )

                camera_instance.Image = camera_instance._obstacle_image
                camera_instance.async_schedule_update_ha_state(force_refresh=True)
                return True

            except HomeAssistantError as e:
                LOGGER.warning(
                    "%s: Unexpected Error processing image: %r",
                    self._file_name,
                    e,
                    exc_info=True,
                )
                return False
        return False

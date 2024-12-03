# Obstacle Detection and Image Processing

## Overview
The Obstacle Detection and Image Processing feature allows users to visualize obstacles detected by their vacuum directly in Home Assistant. This feature is designed for vacuums supporting the `ObstacleImagesCapability` and enables a dynamic experience by switching between map and obstacle views.

## Key Features
- **Dynamic Obstacle Interaction**:
    - Click on detected obstacles in the map view to display their corresponding images.
    - Switch back to the map view by clicking anywhere on the obstacle image.

- **Seamless View Switching**:
    - Switch between map and obstacle views in near real-time is possible thanks to the [Xaiomi Vacuum Map Card](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card).
    - In order to select the obstacle that is highlight in a red dot drawn on the map, it is necessary to add this code to the card configuration:
```yaml
map_modes:
  - other map modes
    ...
  - name: Obstacles View
    icon: mdi:map-marker
    run_immediately: false
    coordinates_rounding: true
    coordinates_to_meters_divider: 100
    selection_type: MANUAL_POINT
    max_selections: 999
    repeats_type: NONE
    max_repeats: 1
    service_call_schema:
      service: mqtt_vacuum_camera.obstacle_view
      service_data:
        coordinates_x: "[[point_x]]"
        coordinates_y: "[[point_y]]"
      target:
        entity_id: camera.YOUR_MQTT_CAMERA_camera
      variables: {}
```

## How It Works
1. **Triggering the Event**:
    - When a user clicks on the map, the frontend card will trigger the action "obstacle_view":
        - `entity_id`: The camera entity to handle the request.
        - `coordinates`: The map coordinates of the clicked point. 
        - The below video demonstrates the feature in action:

    https://github.com/user-attachments/assets/0815fa06-4e19-47a1-9fdc-e12d22449acc

2. **Finding the Nearest Obstacle**:
    - The system locates the nearest obstacle to the given coordinates it isn't necessary to point directly on it.
    - 
3. **Image Download and Processing**:
    - If an obstacle is found, the integration:
        1. Downloads the image from the vacuum.
        2. Resizes it to fit the UI (this will be later improved).
        3. Displays it in the camera view.

4. **Switching Views**:
    - Clicking on an obstacle switches the camera to `Obstacle View`.
    - Clicking any ware obstacle image switches back to `Map View`.

## Configuration
1. Ensure your vacuum supports `ObstacleImagesCapability` and is integrated into Home Assistant.
2. Use a compatible frontend card that allows interaction with map coordinates such the [Xaiomi Vacuum Map Card](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card).

## Notes
### Supported Vacuums
If the vacuum do not support the `ObstacleImagesCapability`, the Camera will simply display the obstacles with a Red Dot on the map, when the Vacuum support Obstacle Detections and has no oboard camera.
If the vacuum supports the capability, the user can interact with the map and view obstacles in near real-time.
This feature was tested on Supervised HA-OS on Pi4 with 8GB RAM and 64GB disk.

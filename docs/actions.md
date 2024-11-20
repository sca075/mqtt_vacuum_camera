# Vacuum Services: Actions and Usage Guide

This document describes the available services for the MQTT Vacuum Camera integration and provides examples of how to use them in your automations or scripts.

---

## 1. **Vacuum Go To**
Moves the vacuum to specific coordinates or a predefined spot.

### Parameters:
| Parameter | Type    | Required | Description                                    |
|-----------|---------|----------|------------------------------------------------|
| `x_coord` | Integer | Yes      | X-coordinate for the vacuum to move to.        |
| `y_coord` | Integer | Yes      | Y-coordinate for the vacuum to move to.        |
| `spot_id` | String  | No       | Predefined point ID for Rand256 vacuums.       |

### YAML Example:
```yaml
service: mqtt_vacuum_camera.vacuum_go_to
data:
  entity_id: vacuum.my_vacuum
  x_coord: 26300
  y_coord: 22500
```
When using the spot_id:
```yaml
service: mqtt_vacuum_camera.vacuum_go_to
data:
  entity_id: vacuum.my_vacuum
  x_coord: 0
  y_coord: 0
  spot_id: "Dock"
```

## 2. **Vacuum Clean Zone**
Starts cleaning in specified zones.

### Parameters:
| Parameter  | Type         | Required | Description                                      |
|------------|--------------|----------|--------------------------------------------------|
| `zone`     | List (Array) | Yes      | List of zones defined as `[x1, y1, x2, y2]`.     |
| `zone_ids` | List         | No       | Predefined zone IDs for Rand256 vacuums.         |
| `repeats`  | Integer      | No       | Number of cleaning repetitions (default: 1).     |

### YAML Example:
Cleaning specific coordinates:
```yaml
service: mqtt_vacuum_camera.vacuum_clean_zone
data:
  entity_id: vacuum.my_vacuum
  zone: [[23510, 25311, 25110, 26362]]
  repeats: 2
```

## 3. **Vacuum Clean Segment**
Starts cleaning in specified segments (rooms).

### Parameters:
| Parameter   | Type         | Required | Description                                      |
|-------------|--------------|----------|--------------------------------------------------|
| `segments`  | List         | Yes      | List of segment IDs or names.                    |
| `repeats`   | Integer      | No       | Number of cleaning repetitions (default: 1).     |

### YAML Example:
Cleaning specific segments:
```yaml
service: mqtt_vacuum_camera.vacuum_clean_segment
data:
  entity_id: vacuum.my_vacuum
  segments: [1, 2, 3]
  repeats: 2
```

Cleaning predefined segment names (Rand256):
```yaml
service: mqtt_vacuum_camera.vacuum_clean_segment
data:
  entity_id: vacuum.my_vacuum
  segments: ["Bedroom", "Hallway"]
  repeats: 1
```

## 4. **Vacuum Map Save**

Save the current map with a specified name (at current Rand256 only).

### Parameters:
| Parameter | Type   | Required | Description                                     |
|-----------|--------|----------|-------------------------------------------------|
| `name`    | String | Yes      | Name of the map to save.                        |

### YAML Example:
```yaml
service: mqtt_vacuum_camera.vacuum_map_save
data:
  entity_id: vacuum.my_vacuum
  map_name: "MY_MAP"
```

### 5. **Vacuum Map Load**

Load a saved map by name (at current Rand256 only).

### Parameters:
| Parameter | Type   | Required | Description                                     |
|-----------|--------|----------|-------------------------------------------------|
| `name`    | String | Yes      | Name of the map to load.                        |

### YAML Example:
```yaml
service: mqtt_vacuum_camera.vacuum_map_load
data:
  entity_id: vacuum.my_vacuum
  map_name: "MY_MAP"
```

When invoking this service, the camera reset the trims and reload the map.

### 6. **Reset Trims**

Resets the map trims for the camera component.

```yaml
service: mqtt_vacuum_camera.reset_trims
```

### 7. **Reload**

Reloads the Integration.

```yaml
service: mqtt_vacuum_camera.reload
``` 

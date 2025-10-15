### Snapshots

This page explains how to create and manage snapshots (PNG images) of the vacuum map.

Status: The built‑in “Export PNG Snapshot” option is deprecated. We recommend using Home Assistant’s camera.snapshot service via automations or scripts. This keeps the integration lightweight and lets you fully control when snapshots are taken.

Where snapshots are stored
- Save snapshots to /config/www so they are served via /local in Lovelace.
- Example path: /www/snapshot_my_vacuum.png → accessible at /local/snapshot_my_vacuum.png

Quick start: recommended automations
1) Snapshot when cleaning starts
```yaml
alias: Vacuum map snapshot on cleaning
trigger:
  - platform: state
    entity_id: vacuum.my_robot
    to: cleaning
action:
  - service: camera.snapshot
    target:
      entity_id: camera.mqtt_vacuum_camera
    data:
      filename: "www/snapshot_vacuum.png"
```

2) Snapshot when docked (post‑clean)
```yaml
a lias: Vacuum map snapshot on docked
trigger:
  - platform: state
    entity_id: vacuum.my_robot
    from: cleaning
    to: docked
action:
  - service: camera.snapshot
    target:
      entity_id: camera.mqtt_vacuum_camera
    data:
      filename: "www/snapshot_vacuum_docked.png"
```

3) Periodic snapshot (every 10 minutes)
```yaml
alias: Periodic vacuum map snapshot
trigger:
  - platform: time_pattern
    minutes: "/10"
action:
  - service: camera.snapshot
    target:
      entity_id: camera.mqtt_vacuum_camera
    data:
      filename: "www/snapshots/map_{{ now().strftime('%Y%m%d_%H%M%S') }}.png"
```

Notes and tips
- Files in /config/www are still auto‑deleted by Home Assistant when the integration is reloaded; rotate or clean them with your own automations if needed.
- You can include the snapshot in notifications by referencing the /local URL.

Legacy behavior (older releases)
- Older versions exposed an “Export PNG Snapshot” option (default: enabled) to drop a PNG into /config/www when the vacuum was idle/docked/error.
- If you still use that option, remember: images aren’t auto‑deleted from /config/www. Disable the option if you no longer want automatic snapshots.

Diagnostics log export (optional)
- When HA debug logging is enabled, a filtered zip of integration logs can be exported from Camera Options. These logs include only this integration’s entries.
- This is optional and unrelated to snapshots via automations.

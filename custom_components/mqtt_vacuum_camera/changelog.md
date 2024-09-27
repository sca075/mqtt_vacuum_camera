# Changelog

## [2024.10.0] - 2024-09-30

### Added
- Detection and incremented support for rand256 vacuums, adding HA sensor for the vacuums.
- Function `build_full_topic_set` for constructing MQTT topic sets.
- Constants `DECODED_TOPICS` and `NON_DECODED_TOPICS` for MQTT topic management.

### Changed
- Updated sensor units and state classes in `sensor.py` for improved measurement reporting.
- Refactored MQTT handling and payload decoding in `connector.py`.
- Removed trailing spaces from strings in `strings.json` and `translations/en.json`.
- Transitioned version from beta to stable release in `camera.py` and `manifest.json`.

### Fixed
- Improved exception handling in `coordinator.py` for broader error management.

Feel free to modify the entries to best reflect the changes made in this release.

# MQTT Vacuum Camera

<p align="center">
  <img width="256" alt="MQTT Vacuum Camera Logo" src="https://github.com/sca075/mqtt_vacuum_camera/assets/82227818/0c623494-2844-4ed9-a246-0ad27f32503e">
</p>

<p align="center">
  <a href="https://github.com/sca075/mqtt_vacuum_camera/releases/latest"><img src="https://img.shields.io/github/release/sca075/mqtt_vacuum_camera.svg?style=popout" alt="Latest Release"></a>
  <a href="https://github.com/sca075/mqtt_vacuum_camera/releases"><img src="https://img.shields.io/github/downloads/sca075/mqtt_vacuum_camera/total" alt="Total Downloads"></a>
  <a href="https://community.home-assistant.io/t/valetudo-vacuums-map-camera-for-home-assistant/600182/19"><img src="https://img.shields.io/static/v1.svg?label=%20&message=Forum&style=popout&color=41bdf5&logo=HomeAssistant&logoColor=white" alt="Community Forum"></a>
  <a href="https://discord.gg/AubW7kQ6F6"><img src="https://img.shields.io/badge/Discord-Join%20Chat-5865F2?logo=discord&logoColor=white" alt="Discord"></a>
  <a href="https://paypal.me/gsca075"><img src="https://img.shields.io/static/v1.svg?label=%20&message=PayPal.Me&logo=paypal" alt="PayPal"></a>
</p>

<p align="center">
  <img src="https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/4f1f76ee-b507-4fde-b1bd-32e6980873cb" alt="MQTT Vacuum Camera Screenshot">
</p>

## Valetudo Vacuum Maps in Home Assistant Made Easy

Display real-time vacuum cleaner maps in Home Assistant for vacuums running [Valetudo Hypfer](https://valetudo.cloud/) or [Valetudo RE (rand256)](https://github.com/rand256/valetudo) firmware. Simple installation via [HACS](https://hacs.xyz/) with guided GUI configuration.

> ❗ **Note:** This is an unofficial project and is not affiliated with [valetudo.cloud](https://valetudo.cloud)

### What You Get

- **Easy Setup**: Install and configure in minutes through Home Assistant's UI
- **Real-time Maps**: Automatically decode and render vacuum maps from MQTT
- **Full Control**: Pair with [lovelace-xiaomi-vacuum-map-card](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card) for complete vacuum control

---

## 🎯 Project Goals

Deliver an out-of-the-box solution for integrating MQTT-based vacuums into Home Assistant, including:
- Real-time map extraction and rendering
- Sensor data (when not provided by the vacuum)
- Control services for seamless operation
- Full vacuum control beyond basic map rendering
- Continuous improvements and regular updates

### 🔗 Related Projects

- **[Valetudo Map Parser](https://github.com/sca075/Python-package-valetudo-map-parser)** - Python library for map extraction
- **[MVC Renderer](https://github.com/sca075/mvc-renderer)** - High-performance C library for map rendering


---

## ✨ Features

<details>
<summary><b>Click to expand full feature list</b></summary>

### Core Features
- ✅ **Universal Support** - All Valetudo-equipped vacuums (Hypfer & Rand256)
- 🌍 **Multi-language** - 14 languages supported (English, Arabic, Chinese, Czech, Dutch, French, German, Italian, Japanese, Polish, Norwegian, Russian, Spanish, Swedish)
- 🤖 **Multiple Vacuums** - Render maps for multiple vacuums simultaneously (e.g., `vacuum.robot1` → `camera.robot1_camera`)
- 🔄 **ON/OFF Control** - Suspend and resume camera stream as needed

### Map Features
- 📸 **[Snapshots](./docs/snapshots.md)** - Save maps using Home Assistant's camera.snapshot service
  ```yaml
  service: camera.snapshot
  target:
    entity_id: camera.valetudo_your_vacuum_camera
  data:
    filename: /config/www/vacuum_map.png
  ```
- 🔄 **Image Rotation** - 0°, 90°, 180°, 270°
- ✂️ **[Auto-Trim](./docs/croping_trimming.md)** - Automatically resize large maps (5210×5210+) with customizable margins
- 🔍 **[Auto-Zoom](./docs/auto_zoom.md)** - Automatically zoom to the room being cleaned
- 🎨 **Customizable Colors** - Configure colors for robot, charger, walls, background, zones, and rooms
- 🌈 **[Transparency Control](./docs/transparency.md)** - Adjust transparency for all elements and rooms
- 📊 **Status Display** - Show vacuum status and current room on the map

### Advanced Features
- 🗺️ **Auto-Generated Calibration** - Automatic calibration points for [lovelace-xiaomi-vacuum-map-card](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card)
- 🏠 **Auto-Generated Rooms** - Automatic room configuration when supported by vacuum
- 🚫 **Zone Visualization** - Display No-Go zones, virtual walls, zone clean areas, and active segments
- 🚧 **[Obstacle Detection](./docs/obstacles_detection.md)** - View obstacles and obstacle images (when supported)
- 🏗️ **Floor Materials** - Detect and render different floor types (wood, tiles, carpets)
- 📡 **Rand256 Sensors** - Pre-configured sensors for complete Home Assistant integration
- 🎮 **[Control Actions](./docs/actions.md)** - Control vacuums without formatting MQTT messages manually

</details>


---

## 📦 Installation

### Quick Install via HACS (Recommended)

[![Open HACS repository in Home Assistant](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=sca075&repository=mqtt_vacuum_camera&category=integration)

### Manual Installation

For detailed installation instructions, including manual setup and configuration of the [lovelace-xiaomi-vacuum-map-card](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card), see our **[Installation Guide](./docs/install.md)**.


---

## ⚙️ Compatibility & System Requirements

<details>
<summary><b>Click to view compatibility information</b></summary>

### Supported Systems
- ✅ **All 64-bit systems** (Raspberry Pi 4+, ProxMox VE, Docker, etc.)
- ❌ **32-bit systems** - Not supported since version 2025.10.0

### Hardware Recommendations
| Hardware | Single Vacuum | Multiple Vacuums |
|----------|---------------|------------------|
| **Raspberry Pi 3 (4GB)** | ✅ Works | ❌ Not recommended |
| **Raspberry Pi 4 (4GB)** | ✅ Works well | ⚠️ Possible, not advised |
| **Raspberry Pi 4 (8GB)** | ✅ Excellent | ✅ Recommended |
| **ProxMox VE / Docker** | ✅ Excellent | ✅ Recommended |

### Supported Vacuums
- ✅ All vacuums running **Valetudo Hypfer** firmware
- ✅ All vacuums running **Valetudo RE (rand256)** firmware
- 💬 Other MQTT-connected vacuums? [Let us know!](https://github.com/sca075/mqtt_vacuum_camera/issues)

### Important Notes
- Extensively tested on Raspberry Pi 4 (8GB) with Home Assistant OS
- Also tested on ProxMox and Docker Supervised environments
- For unsupported platforms, consider [ValetudoPNG](https://github.com/erkexzcx/valetudopng) as an alternative
- Please read our [**NOTICE**](./NOTICE.txt) for additional information

**Your feedback is invaluable!** Please report any issues you encounter on different platforms.

</details>


---

## 🤝 Contributing & Support

We welcome contributions! Whether you can help with code, testing, or documentation, your support is appreciated. Check the Wiki for details on how the camera works and how you can contribute.

### Get Help
- 💬 [Community Forum](https://community.home-assistant.io/t/valetudo-vacuums-map-camera-for-home-assistant/600182/19)
- 💬 [Discord Channel](https://discord.gg/AubW7kQ6F6)
- 🐛 [Report Issues](https://github.com/sca075/mqtt_vacuum_camera/issues)

### Support Development
If you find this integration useful, consider supporting its development:

[![PayPal](https://img.shields.io/static/v1.svg?label=%20&message=PayPal.Me&logo=paypal)](https://paypal.me/gsca075)

---

## 🙏 Acknowledgments

**Thank you** to everyone using this integration and providing feedback, bug reports, and feature suggestions. Your support, understanding, and contributions make this project possible!

---

## 📝 Development Notes

- Developed and tested on Raspberry Pi 4 with [Home Assistant OS](https://www.home-assistant.io/faq/release/) (latest version)
- Also tested on ProxMox VE and Docker Supervised production environments
- Maintained as a solo project with community support

---

## 📄 License

See [NOTICE.txt](./NOTICE.txt) for license information and disclaimers.

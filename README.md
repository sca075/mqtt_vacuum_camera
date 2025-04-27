[releases_shield]: https://img.shields.io/github/release/sca075/mqtt_vacuum_camera.svg?style=popout
[latest_release]: https://github.com/sca075/mqtt_vacuum_camera/releases/latest
[releases]: https://github.com/sca075/mqtt_vacuum_camera/releases
[downloads_total_shield]: https://img.shields.io/github/downloads/sca075/mqtt_vacuum_camera/total

# MQTT Vacuum's Camera
<p align="center">
  <img width="256" alt="logo@2x" src="https://github.com/sca075/mqtt_vacuum_camera/assets/82227818/0c623494-2844-4ed9-a246-0ad27f32503e">
</p>

## Current Release: [![GitHub Latest Release][releases_shield]][latest_release] [![GitHub All Releases][downloads_total_shield]][releases]

![Screenshot 2023-12-27 at 13 37 57](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/4f1f76ee-b507-4fde-b1bd-32e6980873cb)


# Valetudo Vacuums maps in Home Assistant was never so easy.

**About:**
Extract the maps of Vacuum Cleaners connected via MQTT to Home Assistant such as Valetudo [Hypfer](https://valetudo.cloud/) or [RE(rand256)](https://github.com/rand256/valetudo) firmwares, [easy setup](./docs/install.md) thanks to [HACS](https://hacs.xyz/)  and guided Home Assistant GUI configuration.

**What it is:**

❗This is an _unofficial_ repo and is not created, maintained, or in any sense linked to [valetudo.cloud](https://valetudo.cloud)

This custom component is simple to install and setup, decode and render the vacuum maps to Home Assistant in few clicks.
When you want also to control your vacuum you will need to also install the:
[lovelace-xiaomi-vacuum-map-card (recommended)](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card) from HACS as well.

### 🔗 Related Repositories

- [Valetudo Map Extractor (library for extracting the maps)](https://github.com/sca075/Python-package-valetudo-map-parser)

### Goal of this project.
The goal of this project is to deliver an out-of-the-box solution for integrating MQTT-based vacuums into the Home Assistant ecosystem. 
This includes real-time map extraction, sensor data (when not provided), and control services (not available by default)
for a seamless user experience.

Our current focus is evolving beyond map rendering to provide full vacuum control, ensuring a reliable, complete integration for all Valetudo-based vacuums, while continuously improving the user experience through regular updates.  
<details>
   <summary>Planned in the next Release</summary>

In the last releases we did start to implement the Actions for Rand256 and Hypfer.
We can now see the Obstacles Images when available, and somehow we start to organize the code. 
The camera is stable and updated to all requirements of Home Assistant.
Will be also time to take a brake and work in the background, so I do not expect unless required releases in January.

#### 2025.5.0 - **Refactoring and New Additions**
- **Changes**
  - Refactored the code to improve readability and maintainability.
  - Remove file operation routines not required for logging export.
- **Features / Improvements :**
  - Enable loading and saving of maps via services by fully integrating with  [MapLoader](https://github.com/pkoehlers/maploader).
  - Enable selection of specific elements to display on the map..
  - Add options for Area and Floor management.
- **Potential Fixes:**
  - Fix the issue where the absence of a map causes the camera to malfunction.
  - Fix the alpha colours of the elements.
  - Implement a fully coordinated integration of the cameras and sensors.
</details>


### Features:
<details><summary> We here List what this camera offers as futures.</summary>

1) All Valetudo equipped vacuums are supported.
2) Supported languages (English, Arabic, Chinese, Czech, Dutch, French, German, Italian, Japanese, Polish, Norwegian, Russian, Spanish, Swedish).
3) **Automatically Generate the calibration points for the lovelace-xiaomi-vacuum-map-card** to ensure full compatibility to this user-friendly card.
4) **Automatically Generate rooms based configuration when vacuum support this functionality**, this will allow you to configure the rooms quickly on the [lovelace-xiaomi-vacuum-map-card](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card).
5) **The camera take automatically [snapshots](./docs/snapshots.md) (when the vacuum idle/ error / docked)**. It is also possible to save a snapshot using the Action from Home Assistant with the file name and location you want to use. By the default the snapshot is saved in the www folder of Home Assistant. If the snapshot is disabled from Image Options the png will be deleted automatically.
   ```
   service: camera.snapshot
   target:
     entity_id: camera.valetudo_your_vacuum_camera
   data:
     filename: /config/www/REPLACE_ME.png
   ```
6) **Change the image options** directly form the Home Assistant integration UI with a simple click on the integration configuration.
   - **Image Rotation**: 0, 90, 180, 270 (default is 0).
   - [**Trim automatically the images**](./docs/croping_trimming.md). The standard Valetudo images size 5210x5210 or more, are resized automatically (At boot the camera trims and reduces the images sizes). Default margins are 150 pixels, you can customize this value from the image options.
   - Base colors are the **colors for robot, charger, walls, background, zones etc**.
   - **Rooms colors**, Room 1 is actually also the Floor color (for vacuum that do not support rooms).
   - **[Transparency level](./docs/transparency.md) for all elements and rooms** colours can be also customize.
   - It is possible to **display on the image the vacuum status**, this option add a vacuum status text at the top left of the image. Status and room where the vacuum is will be display on the text filed.
7) This integration make possible to **render multiple vacuums** as per each camera will be named with the vacuum name (example: vacuum.robot1 = camera.robot1_camera.. vacuum.robotx = camera.robotx_camera)
8) The camera as all cameras in HA **supports the ON/OFF service**, it is possible to *suspend and resume the camera streem as desired*.
9) In the attributes is possible to get on what room the vacuum is.
10) No Go, Virtual Walls, Zone Clean, Active Segments and Obstacles are draw on the map when available.
11) [Auto Zooming the room (segment)](./docs/auto_zoom.md) when the vacuum is cleaning it.
12) Support Actions "reload" and "reset_trims" implemented for changing the camera settings without restarting Home Assistant.
13) Rand256 sensors are pre-configured from the integration, this will allow you to have all the sensors available in Home Assistant.
14) Added the [**Actions**](./docs/actions.md) for Rand256 / Hypfer to control the vacuums without to format the MQTT messages.
15) [Obstacles](./docs/obstacles_detection.md) are displayed on the map when available. When the vacuum support  ```ObstaclesImage``` is also possible to view the obstacles images.
</details>


### How to install:

[![Open HACS repository in Home Assistant](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=sca075&repository=mqtt_vacuum_camera&category=integration)

The instructions in [here](./docs/install.md) show detailed steps and will help to set up the camera also without HACS (manual setup).
Our setup guide also includes **important** informations on how to setup the [lovelace-xiaomi-vacuum-map-card (recommended)](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card).


### Limitations and Compatibility:
<details>
   <summary>
      Please Read the "Limitations and Compatibility" before to install the camera.
   </summary>

I kindly ask for your understanding regarding any limitations you may encounter with this custom component (please read also
our [**notice**](./NOTICE.txt)).
While it's been extensively tested on a PI4 8GB and now also on ProxMox VE, hardware below PI4 8GB may face issues. **Your feedback on such platforms is invaluable**;
please report any problems you encounter.
As a team of one, I'm diligently working to address compatibility across all environments, but this process takes time. In the interim, you can utilize [ValetudoPNG](https://github.com/erkexzcx/valetudopng) as an alternative on unsupported platforms.
Your support in making this component compatible with all environments is greatly appreciated. If you'd like to contribute, whether through code or time, please consider joining our efforts.
For further details on how the camera operates and how you can contribute, refer to the Wiki section of this project. Your patience and assistance are crucial as we strive toward our goal of universal compatibility.

#### Compatibility:
- PI3 4GB: The camera is working on PI3 4GB, anyhow no chance there to run two vacuums cameras at the same time.
- PI4 4GB: The camera is working on PI4 4GB, anyhow run two vacuums cameras at the same time isn't advised even if possible.
- All Vacuums with Valetudo Hypfer or Rand256 firmware are supported.
- If you have a vacuum with a different firmware connected via MQTT, please let us know, we will try to add the support for it.
</details> 


### Notes:
- This integration is developed and tested using a PI4 with Home Assistant OS fully updated [to the last version](https://www.home-assistant.io/faq/release/), this allows us to confirm that the component is working properly with Home Assistant. Tested also on ProxMox and Docker Supervised "production" enviroment (fully setup home installation).
### Tanks to:
- [@PiotrMachowski](https://github.com/PiotrMachowski) inspiring this integration and his amazing work.
- [@billyourself](https://github.com/billyourself) for providing us the data and motivation to evolve this project.
- [@Skeletorjus](https://github.com/Skeletorjus) that using this integration gave us several ideas to improve it.
- [@rohankapoorcom](https://github.com/rohankapoorcom) autor of the v1.4.0 that make really easy to set up this integration.
- [@gunjambi](https://github.com/gunjambi) that found a solution to re-draw the robot and also implemented the snapshots png to be enabled or disabled from the options.
- [@T0ytoy](https://github.com/T0ytoy) for the superb cooperation in testing our Camera that improved [using the threading](https://github.com/sca075/valetudo_vacuum_camera/discussions/71).
- [@borgqueenx](https://github.com/borgqueenx) for the great cooperation in testing our Camera and helping us to improve it, [see more here](https://github.com/sca075/mqtt_vacuum_camera/discussions/296#:~:text=Edit-,borgqueenx,-2%20weeks%20ago)
- And to all of you using this integration and reporting any issues, improvements and vacuums used with it.

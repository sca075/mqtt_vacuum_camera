[releases_shield]: https://img.shields.io/github/release/sca075/mqtt_vacuum_camera.svg?style=popout
[latest_release]: https://github.com/sca075/mqtt_vacuum_camera/releases/latest

# MQTT Vacuum's Camera
<p align="center">
  <img width="256" alt="logo@2x" src="https://github.com/sca075/mqtt_vacuum_camera/assets/82227818/0c623494-2844-4ed9-a246-0ad27f32503e">
</p>

### Current Release: [![GitHub Latest Release][releases_shield]][latest_release]

![Screenshot 2023-12-27 at 13 37 57](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/4f1f76ee-b507-4fde-b1bd-32e6980873cb)


## Valetudo Vacuums maps in Home Assistant was never so easy.

**About:**
Extract the maps of Vacuum Cleaners connected via MQTT to Home Assistant such as Valetudo [Hypfer](https://valetudo.cloud/) or [RE(rand256)](https://github.com/rand256/valetudo) firmwares, [easy setup](./docs/install.md) thanks to [HACS](https://hacs.xyz/)  and guided Home Assistant GUI configuration.

**What it is:**

❗This is an _unofficial_ repo and is not created, maintained, or in any sense linked to [valetudo.cloud](https://valetudo.cloud)

This custom component is simple to install and setup, decode and render the vacuum maps to Home Assistant in few clicks.
When you want also to control your vacuum you will need to also install the:
[lovelace-xiaomi-vacuum-map-card (recommended)](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card) from HACS as well.

### Goal of this project.
The goal of this project is to deliver an out-of-the-box solution for integrating MQTT-based vacuums into the Home Assistant ecosystem. 
This includes real-time map extraction, sensor data (when not provided), and control services (not available by default)
for a seamless user experience.

Our current focus is evolving beyond map rendering to provide full vacuum control, ensuring a reliable, complete integration for all Valetudo-based vacuums, while continuously improving the user experience through regular updates.  
<details>
   <summary>Planned in the next Release</summary>

#### 2024.12.0 - **Fully implement Coordinator**
- **Features:**
  - Added on 2024.11.0 the Actions for Rand256 to load and save maps fully integrate [MapLoader](https://github.com/pkoehlers/maploader).
  - Fix #263: The init process will be coordinated as we have Cameras and Sensors that need to be initialized.
  - Fix #276 "Unknown error" when some vacuum data is not reachable (refactoring).

</details>

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

- PI3 4GB: The camera is working on PI3 4GB, anyhow no chance there to run two vacuums cameras at the same time.
- PI4 4GB: The camera is working on PI4 4GB, anyhow run two vacuums cameras at the same time isn't advised even if possible.
</details> 


### Known Supported Vacuums:
<details><summary>We here list, thanks to our users and tests done, the known working vacuums.</summary>

- Dreame D9
- Dreame Z10 Pro
- Dreame L10s Ultra
- Mi Robot Vacuum-Mop P
- Roborock.S5 / S50 / S55 (Gen.2)
- Roborock.S6
- Roborock.S7
- Roborock.S8
- Roborock.V1 (Gen.1)
- Xiaomi C1
- In general, **it works with all flashed Valetudo Hypfer or RE(rand256) vacuums**.

</details>


### How to install:

[![Open HACS repository in Home Assistant](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=sca075&repository=mqtt_vacuum_camera&category=integration)

The instructions in [here](./docs/install.md) show detailed steps and will help to set up the camera also without HACS (manual setup).
Our setup guide also includes **important** informations on how to setup the [lovelace-xiaomi-vacuum-map-card (recommended)](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card).

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
</details>


## Notes:
- This integration is developed and tested using a PI4 with Home Assistant OS fully updated [to the last version](https://www.home-assistant.io/faq/release/), this allows us to confirm that the component is working properly with Home Assistant. Tested also on ProxMox and Docker Supervised "production" enviroment (fully setup home installation).
### Tanks to:
- [@PiotrMachowski](https://github.com/PiotrMachowski) inspiring this integration and his amazing work.
- [@billyourself](https://github.com/billyourself) for providing us the data and motivation to evolve this project.
- [@Skeletorjus](https://github.com/Skeletorjus) that using this integration gave us several ideas to improve it.
- [@rohankapoorcom](https://github.com/rohankapoorcom) autor of the v1.4.0 that make really easy to set up this integration.
- [@gunjambi](https://github.com/gunjambi) that found a solution to re-draw the robot and also implemented the snapshots png to be enabled or disabled from the options.
- [@T0ytoy](https://github.com/T0ytoy) for the amazing cooperation in testing our Camera that improved [using the threading](https://github.com/sca075/valetudo_vacuum_camera/discussions/71).
- And to all of you using this integration and reporting any issues, improvements and vacuums used with it.


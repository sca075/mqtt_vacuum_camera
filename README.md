[releases_shield]: https://img.shields.io/github/release/sca075/valetudo_vacuum_camera.svg?style=popout
[latest_release]: https://github.com/sca075/valetudo_vacuum_camera/releases/latest

# Valetudo Vacuum's Camera

![logo_new](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/b1f5a523-7a20-4ddd-b345-84755920458c)

### Current Release: [![GitHub Latest Release][releases_shield]][latest_release]

![Screenshot 2023-12-27 at 13 37 57](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/4f1f76ee-b507-4fde-b1bd-32e6980873cb)


## Valetudo Vacuums maps in Home Assistant was never so easy.

**About:**
Extract the maps for rooted Vacuum Cleaners with Valetudo [Hypfer](https://valetudo.cloud/) or [RE(rand256)](https://github.com/rand256/valetudo) Firmware connected to Home Assistant via MQTT, [easy setup](./docs/install.md) thanks to [HACS](https://hacs.xyz/)  and guided Home Assistant GUI configuration.

**What it is:** 
This custom component anyhow is simple to install and setup, decode and render the vacuum maps to Home Assistant in few clicks. 
When you want also to control your vacuum you will need to also install the:
[lovelace-xiaomi-vacuum-map-card (recommended)](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card) from HACS as well.

### Limitations and Compatibility:
<details>
   <summary>
      Please read the limitations and compatibility before to install the camera.
   </summary>

I kindly ask for your understanding regarding any limitations you may encounter with this custom component.
While it's been extensively tested on a PI4 8GB and now also on ProxMox VE, hardware below PI4 8GB may face issues. **Your feedback on such platforms is invaluable**;
please report any problems you encounter.
As a team of one, I'm diligently working to address compatibility across all environments, but this process takes time. In the interim, you can utilize [ValetudoPNG](https://github.com/erkexzcx/valetudopng) as an alternative on unsupported platforms.
Your support in making this component compatible with all environments is greatly appreciated. If you'd like to contribute, whether through code or time, please consider joining our efforts.
For further details on how the camera operates and how you can contribute, refer to the Wiki section of this project. Your patience and assistance are crucial as we strive toward our goal of universal compatibility.

- PI3 4GB: The camera is working on PI3 4GB, anyhow no chance there to run two vacuums cameras at the same time.
- PI4 4GB: The camera is working on PI4 4GB, anyhow run two vacuums cameras at the same time isn't advised.
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

![Screenshot 2023-09-12 at 22 53 29](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/4f5981e3-39f2-449a-8a43-39870631e9a1)


### How to install:
Via [HACS](https://hacs.xyz//setup/download) please follow. The instructions in [here](./docs/install.md) show detailed steps and will help to set up the camera also without HACS (manual setup). Our setup guide also includes **important** informations on how to setup the [lovelace-xiaomi-vacuum-map-card (recommended)](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card).

### Features: 
<details><summary> We here List what this camera offers as futures.</summary>

1) All Valetudo vacuums are supported.
2) **Automatically Generate the calibration points for the lovelace-xiaomi-vacuum-map-card** to ensure full compatibility to this user-friendly card.
3) **Automatically Generate rooms based configuration when vacuum support this functionality**, this will allow you to configure the rooms quickly on the [lovelace-xiaomi-vacuum-map-card](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card). 
4) **The camera take automatically [snapshots](./docs/snapshots.md) (when the vacuum idle/ error / docked)**. It is also possible to save a snapshot using a service call from Home Assistant with the file name and location you want to use. By the default the snapshot is saved in the www folder of Home Assistant. If the snapshot is disabled from Image Options the png will be deleted automatically.
   ```
   service: camera.snapshot
   target:
     entity_id: camera.valetudo_your_vacuum_camera
   data:
     filename: /config/www/REPLACE_ME.png
   ```
5) **Change the image options** directly form the Home Assistant integration UI with a simple click on the integration configuration.
   - **Image Rotation**: 0, 90, 180, 270 (default is 0).
   - [**Trim automatically the images**](./docs/croping_trimming.md). The standard Valetudo images size 5210x5210 or more, are resized automatically (At boot the camera trims and reduces the images sizes). Default margins are 150 pixels, you can customize this value from the image options.
   - Base colors are the **colors for robot, charger, walls, background, zones etc**.
   - **Rooms colors**, Room 1 is actually also the Floor color (for vacuum that do not support rooms).
   - **[Transparency level](./docs/transparency.md) for all elements and rooms** colours can be also customize.
   - It is possible to **display on the image the vacuum status**, this option add a vacuum status text at the top left of the image. Status and room where the vacuum is will be display on the text filed.
6) This integration make possible to **render multiple vacuums** as per each camera will be named with the vacuum name (example: vacuum.robot1 = camera.robot1_camera.. vacuum.robotx = camera.robotx_camera)
7) The camera as all cameras in HA **supports the ON/OFF service**, it is possible to *suspend and resume the camera streem as desired*.
8) In the attributes is possible to get on what room the vacuum is.
9) No Go, Virtual Walls, Zone Clean, Active Segments and Obstacles are draw on the map when available.
10) [Auto Zooming the room (segment)](./docs/auto_zoom.md) when the vacuum is cleaning it.
</details>


## Notes:
- This integration is developed and tested using a PI4 with Home Assistant OS fully updated [to the last version](https://www.home-assistant.io/faq/release/), this allows us to confirm that the component is working properly with Home Assistant. Tested also on ProxMox and Docker Supervised "production" enviroment (fully setup home installation).
### Tanks to:
- [@PiotrMachowski](https://github.com/PiotrMachowski) inspiring this integration and his amazing work.
- [@Hypfer](https://github.com/Hypfer) for freeing the vacuums from the clouds and continuously improve our vacuums :)
- [@billyourself](https://github.com/billyourself) for providing us the data and motivation to evolve this project.
- [@Skeletorjus](https://github.com/Skeletorjus) that using this integration gave us several ideas to improve it.
- [@rohankapoorcom](https://github.com/rohankapoorcom) autor of the v1.4.0 that make really easy to set up this integration.
- [@gunjambi](https://github.com/gunjambi) that found a solution to re-draw the robot and also implemented the snapshots png to be enabled or disabled from the options.
- [@T0ytoy](https://github.com/T0ytoy) for the amazing cooperation in testing our Camera that improved [using the threading](https://github.com/sca075/valetudo_vacuum_camera/discussions/71).
- And to all of you using this integration and reporting any issues, improvements and vacuums used with it.


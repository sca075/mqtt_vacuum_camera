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

### Sad but True!!
The 2024.06.1 will be the real last relese of this project. 
The project will be archived after this version. Thanks [[Hypfer](https://github.com/home-assistant/brands/pull/5533#), rightly, the new vesion will not have any logo or icons to display, as we aren't affiliated with Hypfer or any Valetudo. Apparently I can't also use the new logo you see above in Home Assistant. 
This project did born just to provide an easy way to display the maps of Valetudo Vacuums (as it is right in the spirit of Home Hassistant).
The decision is for me, sad, but I do not see the point to continue invessting money time on this, also tired to make unproductive discussions.
The repository will be archived, after Home Assistant 2024.6.0, I feel right that the over 200 users that already use this camera have for instance a solid working version.


sted also on ProxMox and Docker Supervised "production" enviroment (fully setup home installation).
### Tanks to:
- [@PiotrMachowski](https://github.com/PiotrMachowski) inspiring this integration and his amazing work.
- [@Hypfer](https://github.com/Hypfer) for freeing the vacuums from the clouds and continuously improve our vacuums :)
- [@billyourself](https://github.com/billyourself) for providing us the data and motivation to evolve this project.
- [@Skeletorjus](https://github.com/Skeletorjus) that using this integration gave us several ideas to improve it.
- [@rohankapoorcom](https://github.com/rohankapoorcom) autor of the v1.4.0 that make really easy to set up this integration.
- [@gunjambi](https://github.com/gunjambi) that found a solution to re-draw the robot and also implemented the snapshots png to be enabled or disabled from the options.
- [@T0ytoy](https://github.com/T0ytoy) for the amazing cooperation in testing our Camera that improved [using the threading](https://github.com/sca075/valetudo_vacuum_camera/discussions/71).
- And to all of you using this integration and reporting any issues, improvements and vacuums used with it.


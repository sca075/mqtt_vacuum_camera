### How to install:
Using [HACS](https://hacs.xyz/) add custom repositories:

![Screenshot 2023-08-12 at 17 06 17](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/4abdf05a-eb50-4317-a0e9-8c6984bdba05)>


please copy the repository link below in ***new repository*** section.
```
https://github.com/sca075/valetudo_vacuum_camera.git
```
![Screenshot 2023-08-12 at 17 25 12](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/5e0874e6-4599-4853-b69b-940609555491)

Select **Integration** as **Category** and click the **Add** button.

Once the repository is added, please click on the repository and the home page will be display. From there you need to
**Download** the integration, [HACS](https://hacs.xyz/) will setup the integration for you. (Note: You can selct here if you want to be notify for beta releases that some time are containg instant fixes).

![Screenshot 2023-08-12 at 17 31 34](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/8ab843a7-be55-4203-b107-c62b64d17032)

You will need to restart Home Assistant at this point to have the integration available. Once Home Assistant will reload, please go in (plase press CTRL clicking the link this shouold open the link in a different tab of your browser) [**Settings** -> **Devices & Services**](https://my.home-assistant.io/redirect/config_flow_start/?domain=valetudo_vacuum_camera) then please confirm to add the integration. The setup wizzard will start.

![Screenshot 2023-08-12 at 18 09 11](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/59f0022e-e233-4311-a6aa-37f17996d6f3)

To know the MQTT topic your_vacuum use you might use the vacuum web GUI.
copy the Topic Prefix/Identifier **only**. Please and past it as a sting in the
vacuum_map required field.

<div align="center">
  <img src="/images/img.png" alt="Valetudo Connections Setting Menu">
</div>
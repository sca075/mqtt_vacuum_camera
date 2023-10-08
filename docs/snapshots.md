### Snapshots ###

**(Please keep in mind that the snapshot image will be not automatically deleted from your www folder while the
PNG export is enable)**

The snapshots images are stored in www (local) folder of HA, by default this function is enable.
It is possible to disable the PNG export from the camera options thanks [@gunjambi](https://github.com/gunjambi)
as soon this option is OFF the PNG will be deleted from the WWW folder.

![Screenshot 2023-10-08 at 16 31 03](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/00a082b1-f8a5-4cf3-93a9-93110b060ef5)


When the vacuum battery get empty because of an error during a cleaning cycle, or in different conditions as per the below example.
If the PNG data store is enable will be possible to create an automation to send the screenshot to your mobile. 
The snapshot PNG is updated when the vacuum changes status to idle, error or docked (at the end of the cycle).
When using the below example HA editor please edit the automation in yaml because the snapshot attribute (used in this example)
provides boolean values True or False.
HA editor will translate to "True" (string) from the UI editor, home assistant will not notify you in this case.

**(Please keep in mind that the snapshot image will be not automatically deleted from your www folder while the
PNG export is enable)**

```

alias: vacuum notification
description: ""
trigger:
  - platform: state
    entity_id:
      - camera.v1_your_vacuum_camera
    attribute: snapshot
    from: false
    to: true
condition: []
action:
  - service: notify.mobile_app_your_phone
    data:
      message: Vacuum {{states("vacuum.valetudo_your_vacuum")}}
      data:
        image: /local/snapshot_your_vacuum.png
mode: single

```

*Aside the image, this function store also a zip file with diagnostic data on the www folder, we filter the data relative to this integration from the HA logs and those data are stored only if the
log debug function in HA is active ***(we don't store any data in the www folder if the user do not log the data)***.*

![Screenshot 2023-10-03 at 06 55 36](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/6aedcdd3-6f39-4b11-8c0f-6da99f5490e9)

![Screenshot 2023-10-03 at 06 58 36](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/363881f5-bca6-462f-80d8-9a6351bcf285)

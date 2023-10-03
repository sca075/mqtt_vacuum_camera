### Snapshots ###

**(please keep in mind that the snapshot image will be not automatically deleted from your www folder)**:

The snapshots images are stored in www (local) folder of HA. It is therefore possible to create an automation to send the screenshot to your mobile in different conditions as per the below example. 
When the vacuum changes status to idle, error or docked (at the end of the cycle), the camera snapshot the current position. 
When using HA editor please edit the automation in yamil because the snapshot attribute provides boolean values True or False. 
HA editor will translate to "True" (string) from the UI editor, home assistant will not notify you in this case.

It will be soon possible to enable or disable the snapshots (images) anyhow **please keep in mind that the snapshot image will be not automatically deleted from your www folder if you do not disable this function**:

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

*Aside the image, this function will store also a zip file with diagnostic data on the www folder, we filter the data relative to this integration from the HA logs and those data are stored only if the
log debug function in HA is active ***(we don't store any data in the www folder if the user do not log the data)***.*

![Screenshot 2023-10-03 at 06 55 36](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/6aedcdd3-6f39-4b11-8c0f-6da99f5490e9)

![Screenshot 2023-10-03 at 06 58 36](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/363881f5-bca6-462f-80d8-9a6351bcf285)

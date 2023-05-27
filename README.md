# valetudo_vacuum_mapper
## Integration for Valetudo Vacuums to Home Assistant

### Acutal Status is: Tested Camera image retrival


**background idea**:
At today there is the possibility to connect the Vacuum Cleaners with Valetudo Firmware to Home Assistant via MQTT with have limited options. 
This Custom Component allow to integrate the Vacuum functionalities and encode the Vacuum map. 
The integration in the end will provide all sensors and maps data so that is possible to custom select the area to be cleaned, 
go to a specific location, check and reset the consumables counters for maintenance purpose. 

At current only the map can be display simply adding to configuration.yaml:

```
camera:
    - platform: valetudo_vacuum_camera
        vacuum_entity: "vacuum.your_vacuum"
        vacuum_map: "valetudo/your_vacuum/MapData/map-data-hass"
        MQTT_User: "broker_user_name"
        MQTT_Password: "broker_password"
        scan_interval:
            seconds: 5
```

To test this custom component we are using a PI4 with Home Assistant OS.
 
**The current tasks list is:**
- [ ] Get from the json data predicted_path and selected_area. 
- [ ] Grab the available consumable data form MQTT.
- [ ] Fix config_flow in order to meet HA requirements.
- [ ] Create the Services to go_to and area_clean (auto format MQTT message to publish).
- [ ] Work out the card to manage the camera image, select area and go to function.


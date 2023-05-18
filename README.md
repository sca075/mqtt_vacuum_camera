# valetudo_vacuum_mapper
Integration for Valetudo Vacuums to Home Assistant

Acutal Status is: Development (not released)

backround idea:
Possibility to connect the Vacuum Cleaners with Valetudo Firmware to Home Assistant via MQTT that have righit now limited options. 
This Custom Component will allow to integrate the Vacuum functionality and show the Vacuum Position and controls of the Vacuum. 
The integration in the end will provide all sensors and maps data so that is possible to custom select the area to be cleaned, 
go to a specific location, check and reset the consumables counters for maintenance purpose. 
It will allow also to easy estract the required MQTT commands to define the services calls in the automations or scpits that involve the vacuum, with a simple vacuum.go_to or vacuum.clean_segment additional service. As per the vacuum cleaner used for the developement of this component do not supports rooms cleaning, we would implement this functionalities as well uppon cooperation and data submition.

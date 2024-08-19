# Automating Trimming Function:
Valetudo images are normally quite huge, this results in a heavy handling of the images. 
Some vacuums also produces so big images that could seriously affect the way HA works (sometimes also crash it).
For a practical and more convenient way to automate the vacuums with HA this integration will automatically trim the images.

This is an image at 100% (full size):

![Screenshot 2023-08-18 at 10 33 05](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/983d0848-e3b5-4db6-8957-f25bc6cd073f)

For this reason the camera trim automatically the  images. By default the image have 100 pixel of margins, the trimming factor is automatically calculated at camera startup and will be saved to avoid to recompute it at each reboot.

![Screenshot 2023-08-18 at 11 18 24](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/b6d57424-a9f2-4d67-964e-693718cc66a9)

### How this works:
1) Trims are automatically calculated by searching the fist pixel not having the background colour in the image. This could be possible that the trims are not perfectly calculated because of the lidar data (above image is an example).
2) The result image can be rotated by 0, 90, 180, 270 degrees.
3) It is possible to enlarge or set the margins to be smaller, default the margins of the images are 100 pixels.
4) After the frame 0, from frame 1 actually, as the trims are stored in memory will be re-use each time the image is composed.
5) The trims are then saved in json format in the .storage folder of Home Assistant.
It is possible therefore to optimize the view to display the map without, virtually, empty spaces around currently using the card.
6) Is also possible to select the image aspect ratio as desired.

![Screenshot 2024-03-13 at 17 18 30](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/016e4282-2d4a-4cee-a4b7-b3dbf8558898)

If this isn't giving the expected result, there is the possibility to add a Trim offset to the image. This will allow to move the trims to the desired position.
It is considered that the image is at 0 degrees rotation, the trims are calculated from the top left corner of the image.
Camera Options -> Advanced -> Configure Offset Image

![Screenshot 2024-08-19 at 11 26 04](https://github.com/user-attachments/assets/7a91da26-1dff-446c-bd79-0a6ab952630d)

As per the trims are saved and reloaded at each startup, when you need to change the map of the vacuums (using [maploader](https://github.com/pkoehlers/maploader) or as [per reported for Rand256](https://github.com/sca075/mqtt_vacuum_camera/discussions/236))
you can reset the trims with the Action "reset_trims" available in the Camera.

```yaml
action: mqtt_vacuum_camera.reset_trims
data: {}
```

This Action will delete the stored trims and when the vacuum is __Docked__ re-store them from the new image and will also reload the Camera to apply the new trims.

The calibrations points of the maps will be automatically updated at each map transformations. 
The robot position and coordinates will not change, meaning that there will be no functional changes for the pre-defined cleaning areas or segments (rooms).

### Note:
If you want to get the most from the auto cropping and your vacuum support segments, setting the room_0 to the same colour of the background should remove the lidar imperfections.

![Screenshot 2023-12-27 at 13 21 52](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/b830f3d9-9e60-4206-a03c-146c14f89121)

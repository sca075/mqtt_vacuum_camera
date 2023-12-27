### Cropping Function:
Valetudo images are normally quite huge, this results in a heavy handling of the images. 
Some vacuums also produces so big images that could seriously affect the way HA works (sometimes also crash it).
For a practical and more convenient way to automate the vacuums with HA this integration will automatically trim the images.

At 100% the images will be display at full size:

![Screenshot 2023-08-18 at 10 33 05](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/983d0848-e3b5-4db6-8957-f25bc6cd073f)

At 50% (camera default cropping factor) this image will be rendered as below:

![Screenshot 2023-08-18 at 10 38 49](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/b91bac5e-79da-4257-9f44-4ba64aa6478d)

### Automating Trimming Function:

![Screenshot 2023-08-18 at 10 44 40](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/993c5728-6652-4079-9eb0-ad6c03ef2b28)

From v1.3.2 was possible to trim the resulting image after cropping. Cropping and Trimming options was available till v1.4.9. By default from v1.5.0 aorund the image there are 150 pixel of margins, the trimming factor is automatically calculated at camera startup.

![Screenshot 2023-08-18 at 11 18 24](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/b6d57424-a9f2-4d67-964e-693718cc66a9)

In summary our specification is now:
1) Trims are automatically calculated by searching the fist pixel not having the background colour in the image. This could be possible that the trims are not perfectly calculated because of the lidar data (above image is an example).
2) The result image can be rotated, this can result in larger maps.
3) It is possible to enlarge or set the margins to be smaller, default the margins of the images are 150 pixels.
4) After the frame 0, from frame 1 actually, as the trims are stored in memory will be re-use each time the image is composed. 
It is possible therefore to optimize the view to display the map without, virtually, empty spaces around currently using the card.

The calibrations points of the maps will be automatically updated at each map transformations. 
The robot position and coordinates will not change, meaning that there will be no functional changes for the pre-defined cleaning areas or segments (rooms).

If you want to get the most from the auto cropping and your vacuum support segments, setting the room_0 to the same colour of the background will remove the lidar imperfections.

![Screenshot 2023-12-27 at 13 21 52](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/b830f3d9-9e60-4206-a03c-146c14f89121)

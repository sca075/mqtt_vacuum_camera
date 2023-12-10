### Cropping Function:
Valetudo images are normally quite huge, this results in an heavy handling of the images. 
Some vacuums also produces so big images that could seriusly effect the way HA works (sometimes also crash it).
For a practical and more convenient way to automate the vacuums with HA this integration have the possibility to crop the images.

At 100% the images will be display at full size:

![Screenshot 2023-08-18 at 10 33 05](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/983d0848-e3b5-4db6-8957-f25bc6cd073f)

At 50% (camera default cropping factor) this image will be rendered as below:

![Screenshot 2023-08-18 at 10 38 49](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/b91bac5e-79da-4257-9f44-4ba64aa6478d)

The options of the integration can be of course configured in HA but value 50% is the minimum we can set as per performance wise below this value there could be some issue in Home Assistant. 

![Screenshot 2023-08-18 at 10 44 40](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/993c5728-6652-4079-9eb0-ad6c03ef2b28)

the copping percentage will be 100% = Full image.. therefore the image is scaled.. or cropped to the x% of the original size.
This mean 0% is no image at all. You can optimize the image so that you get the vacuum map zoomed as closer it is possible.
As reference, 50% for the image on this guide..

### Automating Trimming Function:

From v1.3.2 was possible to trim the resulting image after cropping. This option was available till v1.4.9.

![Screenshot 2023-08-18 at 11 13 17](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/b9add7a8-c3ed-4307-8a8e-1778cfb36f1d)

The value we specify for the trimming was refer as pixels amount.
On the test image (cropped at 25%) removing 350 pixels from top of the image we will obtain:

![Screenshot 2023-08-18 at 11 18 24](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/b6d57424-a9f2-4d67-964e-693718cc66a9)

As per this option was difficult to use, we simplify it adding simply the margins we want around the image.
This function available from v1.5.0 will automatically calculate the required trim amount, in the debug log is possible to see the calculated values.
In summary our specification is now:
1) The Cropping factor 50% is the default value the Camera use. It isn't possible to reduce it but still possible to increase this value.
2) The trims are automatically calculated, as per, we search the fist pixel not having the background colour in the image it could be possible that the trims are not perfectly calculated because of the lidar data (above image is an example).
3) The result image can be rotated, this can result in larger maps.
4) It is possible to enlarge or set the margins to be smaller, default the margins of the images are 150 pixels.
It is possible therefore to optimize the view to display the map without, virtually, empty spaces around.

The calibrations points of the maps will be automatically updated at each map transformations. 
The robot position and coordinates will not change, meaning that there will be no functional changes for the pre-defined cleaning areas or segments (rooms).

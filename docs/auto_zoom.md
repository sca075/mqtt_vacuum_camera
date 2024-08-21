### Auto Zooming the room (segment) when the vacuum is cleaning it.

***Category:*** Camera Configuration - Image Options - Auto Zoom

![Screenshot 2024-03-13 at 17 17 13](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/e228fc96-8e95-4be9-af9e-b21a259e8289)

![Screenshot 2024-03-13 at 17 14 10](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/390a5a85-3091-40b0-9846-c0bc9c6db93d)

***Default:***  Disable

***Description:*** If the vacuum supports the segments and those are properly configured also in the card, when the
vacuum enters the room to clean the Camera will zoom the image on that room. The full zoom will change the aspect ratio of the image.
Below exaple of how looks the dashboad when the ratio isn't locked.

https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/99fc5b9b-20a5-4458-8f5c-1dda874a9da5

With the Lock Aspect Ratio function the image is displayed with the selected ratio (this is at orinal image ratio).

https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/6930e76a-9c66-4f81-b824-003698160ffd

While auto zooming the segments the images will change aspect ratio if the lock aspect ratio is disabled.
If enabled the aspect ratio will be kept and the image will be padded to fit the aspect ratio.
It is also possible to select the desired aspect ratio of the images independently of the auto zoom.
See the Image Options guide for more details.

***Note:*** The zoom works only when the vacuum is in “cleaning” state. In all other states the image returns
automatically to the floor plan. If the auto zoom is disabled the floor map is displayed normally, cleaned or in clean
mode segments are highlighted on the map by a faded selected color.

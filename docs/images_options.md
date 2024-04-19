### Image Options.

***Category:*** Camera Configuration

![Screenshot 2024-03-09 at 21 18 47](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/02787561-6c1b-4db7-9960-fd8f3e911161)

***Description:*** The camera configuration is a set of options that can be used to customize the camera image. The
options are:

***1.*** Image Rotation.

The image can be rotated in 90 degrees steps. The dropdown list allows to select the desired rotation.

![Screenshot 2024-03-13 at 17 16 40](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/8e1a9716-de6e-4f8f-bb66-fdb9c6ad8834)

***2.*** Margins.

The images are pre-processed to remove unused maps areas, there is a function that automatically trims the images to get
the optimal view of the maps. This function will search for non background color pixels, resulting basically without
margins. This value add the pixels at each side of the image. Default is 100 pixels.

![Screenshot 2024-03-13 at 17 17 13](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/e228fc96-8e95-4be9-af9e-b21a259e8289)

***3.*** Image offset

The image offset option, will cut the Lidar impefections from the images. This option used with the auto-trim will reduce the image size, that anyway can be keep at desired aspect ratio. The below video explain how to resize the image, the menu values are design to _work at rotation 0_ .

https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/4e1cee93-2ccd-413e-8cfa-79f4dcf76635


***4.*** Aspect Ratio.

The aspect ratio of an image after [pre-processing](https://github.com/sca075/valetudo_vacuum_camera/blob/main/docs/croping_trimming.md)  should be 2:1. Anyway as per the layout
differ on each floor, it could be possible it would result on different aspect ratio. This option allows to select the
desired aspect ratio of the images. The aspect ratio is the ratio of the width to the height of the image.
By default, the Camera use the Original Ratio of the image.
Be sure to **_lock the aspect ratio_**  if you want to keep the selected aspect ratio.

![Screenshot 2024-03-13 at 17 18 30](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/016e4282-2d4a-4cee-a4b7-b3dbf8558898)

***5.*** Auto Zoom and Lock Aspect Ratio.

[Auto Zooming the room (segment)](
https://github.com/sca075/valetudo_vacuum_camera/blob/main/docs/auto_zoom.md) when the vacuum is cleaning it. The full zoom will change the
aspect ratio of the image. This why it is possible to lock the aspect ratio of the image to keep the selected ratio and
preserve the Dashboards layout.
Independently from the Auto Zoom as above **Lock Aspect Ratio** should be active when selecting the desired image Aspect
Ratio.

![Screenshot 2024-03-13 at 17 14 10](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/fb283c47-12e3-42db-b86e-47f3d0f77efa)

***6.*** Export PNG snapshots.

The camera will shoot automatically snapshots of the maps and save them in the folder `www` of the Home Assistant. The
images are saved in PNG format and named like this example `snapshot_your_vacuum.png`. Disabling this function will
delete and do not save in the images in `www` folder. See [Snapshots](https://github.com/sca075/valetudo_vacuum_camera/blob/main/docs/docs/snapshots.md) for more details.

![Screenshot 2024-03-13 at 17 19 15](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/52a47822-9588-4a8d-9d7f-adaf1a6e2f90)


### Cropping Function:
Valetudo images are normally quite huge, this results in an heavy handling of the images. 
Some vacuums also produces so big images that could seriusly effect the way HA works (sometimes also crash it).
For a prattical and more convinient way to automate the vacuums with HA this integration have the possibility to crop the images.

Att 100% the images will be display at full size:

![Screenshot 2023-08-18 at 10 33 05](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/983d0848-e3b5-4db6-8957-f25bc6cd073f)

At 50% (camera default cropping factor) this image will be rendered as below:

![Screenshot 2023-08-18 at 10 38 49](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/b91bac5e-79da-4257-9f44-4ba64aa6478d)

The options of the integration can be of course configured in HA. 

![Screenshot 2023-08-18 at 10 44 40](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/993c5728-6652-4079-9eb0-ad6c03ef2b28)

the copping percentage will be 100% = Full image.. therefore the image is scaled.. or cropped to the x% of the original size.
This mean 0% is no image at all. You can optimize the image so that you get the vacuum map zoomed as closer it is possible.
As reference, 25% for the image on this guide.. will result as below:

![Screenshot 2023-08-18 at 11 00 43](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/9c5b5502-83ee-4445-aac6-da3ba0e2087e)

Overcopped images instead will be resulting as below (the blue area is the total image) in incople maps.

![Screenshot 2023-08-18 at 11 03 53](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/2ac2e8d9-7453-40e9-a2d4-0eba48de4699)


### Trimming Function:

Introuduced on v1.3.2 there is also the possibilty to trim the resulting image after cropping.

![Screenshot 2023-08-18 at 11 13 17](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/b9add7a8-c3ed-4307-8a8e-1778cfb36f1d)

The value we specify for the trimming is refered as pixels ammount.
On the test image (previusly cropped at 25%) removing 350 pixesels from top of the image we will obtain:

![Screenshot 2023-08-18 at 11 18 24](https://github.com/sca075/valetudo_vacuum_camera/assets/82227818/b6d57424-a9f2-4d67-964e-693718cc66a9)


It is possile therefore to optimize the view to dsiplay only the map (without empty spacess arround it).

The calibrations points of the maps will be automatically updated at each map transformations. 
The robot positon and coordinates will not change, maing that thre will be no changes on whatver cleaning area pre-defined.

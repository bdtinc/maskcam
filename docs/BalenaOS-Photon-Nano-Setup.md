# BalenaOS Setup Instructions for MaskCam on Jetson Nano with Photon Carrier Board

BalenaOS is a very light weight distribution designed for running containers on edge devices. It has a number of advantages for fleet deployment and management, especially when combined with balena's balenaCloud mangament system. Explaining the details of how to set up balenaCloud applications is beyond the scope of this document, but you can test MaskCam on balenaOS using a local development environment setup.

When using a Jetson Nano with a Photon carrier board (i.e. a "Photon Nano"), the process for installing balenaOS is different than with a Developer Kit. The production Jetson Nano module does not have an SD card slot, so balenaOS has to be directly flashed onto the device over USB, rather than using balenaEtcher. Fortunately, balena has created a flashing tool called [jetson-flash](https://github.com/balena-os/jetson-flash) that allows you to do this.


### Setting up jetson-flash
To flash the balenaOS image onto the Photon Nano, we need to use Balena's jetson-flash tool. The instructions here show how to install and use jetson-flash on an Ubuntu v18.04 PC. The tool also requires NodeJS >= v10, which can be installed on Ubuntu using [these installation instructions](https://github.com/nodesource/distributions/blob/master/README.md#installation-instructions).

First, clone the jetson-flash repository using:

```
git clone https://github.com/balena-os/jetson-flash.git
```

Next, go to the [balenaOS download page](https://www.balena.io/os/#download) and download the CTI Photon Nano Development image. Unzip the image, and move it to the jetson-flash directory.

Then, from inside the `jetson-flash` directory, issue the following command to download the NodeJS package dependencies.

```
npm install
```

Now jetson-flash is ready to be used to flash the OS image onto the Photon Nano.

### Flashing balenaOS onto the Jetson Nano over USB
Before flashing the OS, the Photon Nano has to be powered on and put into Force Recovery as shown in the [Photon manual](https://connecttech.com/ftp/pdf/CTIM_NGX002_Manual.pdf). Starting with a Photon carrier board that has a Jetson Nano module installed, plug in 12V power to the barrel jack on the carrier board. Then, press and hold SW2 for at least 10 seconds.

Plug a micro-USB cord from the Ubuntu PC to P13 on the bottom side of the Photon carrier board. Verify the board is in Force Recovery mode by issuing `lsusb` and checking that an Nvidia device is listed. If it isn't, try re-connecting the USB cable and repeating the process to put the board in Force Recovery mode.

Begin flashing by issuing the following command, where `balena.img` is replaced with the filename for the image that was downloaded and extracted previously.

```
sudo ./bin/cmd.js -f balena.img -m jetson-nano-emmc
```

This will initiate the flashing process, which takes about 10 minutes. Once it's complete, unplug the micro-USB cable and power cycle the Photon carrier board. Plug an Ethernet cable into the Photon to connect it to a local network.

### Installing balena CLI

Use [these instructions](https://github.com/balena-io/balena-cli/blob/master/INSTALL.md) to install the balena CLI tool on your Ubuntu PC.

### Connecting to your Jetson

On the Ubuntu PC, open a terminal and run:
```
sudo balena scan
```

This will report the IP address of your Photon Nano. Use this IP address with the following command to connect to your Jetson:

```
balena ssh <device ip>
```

At this point you are in a console as root user on your Jetson running balenaOS. Now, we just need to download the docker container and run it! On balenaOS, "docker" is replaced by "balena", as shown in the following command. Issue the two commands below to download and run MaskCam:

```
$ balena pull maskcam/maskcam-beta
$ balena run --privileged --rm -it --env MASKCAM_DEVICE_ADDRESS=<device ip> -p 1883:1883 -p 8080:8080 -p 8554:8554 maskcam/maskcam-beta
```

Note that setting `MASKCAM_DEVICE_ADDRESS` is optional, and you can also set other configuration parameters exactly as indicated in the [device configuration](https://github.com/bdtinc/maskcam#setting-device-configuration-parameters) section of the main docs.

### Using balenaCloud
You can create a free balenaCloud account that will allow you to link up to 10 devices, in order to test some of the most useful features that this platform provides.
You'll need to create an App, install the balena CLI and then follow these instructions in order to deploy the maskcam container to your app:

https://www.balena.io/docs/learn/deploy/deployment/

For a simple use case, you can just use the `balena push myApp` command from the root directory of this project (it will take a long time while it builds and pushes the whole image), but you should familiarize yourself with the platform and use the deployment method that better fits your needs.

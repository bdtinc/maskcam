# BalenaOS Developer Kit Nano Setup Instructions for MaskCam

BalenaOS is a very light weight distribution designed for running containers on edge devices. It has a number of advantages for fleet deployment and management, especially when combined with balena's balenaCloud mangament system. Explaining the details of how to set up balenaCloud applications is beyond the scope of this document, but you can test MaskCam on balenaOS using a local development environment setup.
Except for installing balenaOS and using a slightly modified launch command, this process is essentially the same as the Jetson Nano Development kit instructions from [the main README](https://github.com/bdtinc/maskcam#running-maskcam-from-a-container-on-a-jetson-nano-developer-kit).

If you want to use balenaCloud instead (i.e: see your device in the web dashboard), and you're willing to take some time to push the container to your own account, check [Using balenaCloud](#using-balenacloud) at the end of this section.

In any case, this will require a Jetson Nano Development Kit, a 32 GB or higher Micro-SD card, and another computer (referred to here as main system) on the same network.

### Installing balenaOS
As mentioned, this procedure will not link your device with a balenaCloud account, but instead it will enable local development.

First, go to https://www.balena.io/os/, scroll to the Download section, and download the development version for Nvidia Jetson Nano SD-CARD.

Next, go to https://www.balena.io/etcher/ and install balenaEtcher.

In balenaEtcher, simply select the zip file you downloaded, and after inserting the sd card into your main system select it, then press the 'Flash!' icon.

After the flashing process is completed, place the sd card into your Jetson Nano Development Kit, ensure the network cable is plugged into the device and power up the Jetson.

### Installing balena CLI

Use [these instructions](https://github.com/balena-io/balena-cli/blob/master/INSTALL.md) to install the balena CLI tool.

### Connecting to your Jetson

First, in a terminal on your main system run the command:
```
sudo balena scan
```
Note the ip address in the result.

Next connect to your Jetson:
```
balena ssh <device ip>
```

At this point you are in a console as root user on your Jetson running balenaOS. The commands from this point on are exactly the same as the instructions for running using JetPack on the Nano Developer Kit with the following differences.
1. The `docker` command is replaced by `balena`
2. Do not use the `--runtime nvidia` switch. It is automatic on balenaOS for Jetson and you will get errors if you include it.

So issuing the following commands will run MaskCam:
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

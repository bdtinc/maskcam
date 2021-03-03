# MaskCam <!-- omit in toc -->
MaskCam is a reference design for a Jetson Nano-based smart camera system that measures crowd face mask usage in real-time, with all AI computation performed at the edge. MaskCam detects and tracks people in its field of view and determines whether they are wearing a mask via an object detection, tracking, and voting algorithm. It uploads statistics (not videos) to the cloud, where a web GUI can be used to monitor the face mask compliance in the field of view. It saves interesting video snippets to local disk (e.g., a sudden influx of lots of people not wearing masks) and can optionally stream video via RTSP.

MaskCam can be run on a Jetson Nano Developer Kit, or on a Jetson Nano SOM with the ConnectTech Photon carrier board.  It was designed to use the Raspberry Pi High Quality Camera but will also work with pretty much any USB webcam.

The on-device software stack is mostly written in Python and runs under JetPack 4.4.1 or 4.5. Edge AI processing is handled by NVIDIA’s DeepStream video analytics framework, YOLOv4-tiny, and Tryolab's Norfair tracker.  MaskCam reports statistics to and receives commands from the cloud using MQTT and a web-based GUI. The software is containerized and for evaluation can be easily installed on a Jetson Nano DevKit using docker with just a couple of commands. For production, MaskCam can run under BalenaOS, which makes it easy to manage and deploy multiple devices.

We urge you to try it out! It’s easy to install on a Jetson Nano Dev Kit and requires only a web cam. (The cloud-based statistics server and web GUI are optional, but are also dockerized and easy to install on any reasonable Linux system.)  [See below for installation instructions.](https://github.com/tryolabs/bdti-jetson#running-maskcam-from-a-container-on-a-jetson-nano-developer-kit)

MaskCam was developed by Berkeley Design Technology, Inc. (BDTI) and Tryolabs S.A., with development funded by NVIDIA. MaskCam is offered under the MIT License. For more information about MaskCam, please see the forthcoming white paper from BDTI.

## Table of contents <!-- omit in toc -->
- [Start Here!](#start-here)
  - [Running MaskCam from a Container on a Jetson Nano Developer Kit](#running-maskcam-from-a-container-on-a-jetson-nano-developer-kit)
  - [Viewing the video streaming](#viewing-the-video-streaming)
  - [Setting device configuration parameters](#setting-device-configuration-parameters)
  - [Troubleshooting](#troubleshooting)
    - [Error: camera not connected/not recognized](#error-camera-not-connectednot-recognized)
    - [Error: not running in privileged mode](#error-not-running-in-privileged-mode)
    - [Error: reason not negotiated/camera capabilities](#error-reason-not-negotiatedcamera-capabilities)
    - [Error: Streaming or file server are not accessible (nothing else seems to fail)](#error-streaming-or-file-server-are-not-accessible-nothing-else-seems-to-fail)
    - [Other Errors](#other-errors)
- [MQTT Server Setup](#mqtt-server-setup)
  - [Running the MQTT Broker and Web Server](#running-the-mqtt-broker-and-web-server)
  - [Setup a device with your server](#setup-a-device-with-your-server)
  - [Checking MQTT connection](#checking-mqtt-connection)
- [Accessing the MaskCam container](#accessing-the-maskcam-container)
  - [Development mode: manually running MaskCam](#development-mode-manually-running-maskcam)
  - [Debugging: running MaskCam modules as standalone processes](#debugging-running-maskcam-modules-as-standalone-processes)
- [Building from Source on Jetson Nano Developer Kit](#building-from-source-on-jetson-nano-developer-kit)
- [Running on Jetson Nano Developer Kit using balenaOS](#running-on-jetson-nano-developer-kit-using-balenaos)
- [Running on Jetson Nano with Photon carrier board](#running-on-jetson-nano-with-photon-carrier-board)
- [Useful development scripts](#useful-development-scripts)


## Start Here!
### Running MaskCam from a Container on a Jetson Nano Developer Kit
The easiest and fastest way to get MaskCam running on your Jetson Nano Dev Kit is using our pre-built containers.  You will need:

1. A Jetson Nano Dev Kit running JetPack 4.4.1 or 4.5
2. An external DC 5V, 4A power supply connected through the Dev Kit's barrel jack connector (J25). (See [these instructions](https://www.jetsonhacks.com/2019/04/10/jetson-nano-use-more-power/) on how to enable barrel jack power.) This software makes full use of the GPU, so it will not run with USB power.
3. A USB webcam attached to your Nano
4. Another computer with a program that can display RTSP streams -- we suggest [VLC](https://www.videolan.org/vlc/index.html) or [QuickTime](https://www.apple.com/quicktime/download/).

First, the MaskCam container needs to be downloaded from Docker Hub. On your Nano, run:
```
# This will take 10 minutes or more to download
sudo docker pull maskcam/maskcam-beta
```

Find your local Jetson Nano IP address using `ifconfig`. This address will be used later to view a live video stream from the camera and to interact with the Nano from a web server.

Make sure a USB camera is connected to the Nano, and then start MaskCam by running the following command. Make sure to substitute `<your-jetson-ip>` with your Nano's IP address.
```
# Connect USB camera before running this!
sudo docker run --runtime nvidia --privileged --rm -it --env MASKCAM_DEVICE_ADDRESS=<your-jetson-ip> -p 1883:1883 -p 8080:8080 -p 8554:8554 maskcam/maskcam-beta
```

The MaskCam container should start running the `maskcam_run.py` script, using the USB camera as the default input device (`/dev/video0`). It will produce various status output messages (and error messages, if it encounters problems). If there are errors, the process will automatically end after several seconds. Check the [Troubleshooting](#troubleshooting) section for tips on resolving errors.

Otherwise, it should continually generate status messages (such as `Processed 100 frames...`). Leave it running (don't press `Ctrl+C`) and continue to the next section to visualize the video!

### Viewing the video streaming
If you scroll through the logs and don't see any errors, you should find a message like:

```Streaming at rtsp://aaa.bbb.ccc.ddd:8554/maskcam```

where `aaa.bbb.ccc.ddd` is the address that you provided in `MASKCAM_DEVICE_ADDRESS` previously. (If you didn't provide an address, you'll see some unknown address label there.)

You can copy-paste that URL into your RSTP streaming viewer (such as VLC) on another computer. The gif below shows how to initiate streaming with VLC. If all goes well,
you should be rewarded with streaming video of your Nano, with green boxes around faces wearing masks and red boxes around faces not wearing masks.

*Insert recorded gif of starting streaming on VLC*

This video stream gives a general demonstration of how MaskCam works. However, MaskCam also has other features, such as the ability to send mask detection statistics to the cloud and view them through a web browser. If you'd like to see these features in action, you'll need to set up an MQTT server, which is covered in the [MQTT Server Setup section](#mqtt-server-setup).

### Setting device configuration parameters
MaskCam uses environment variables to configure parameters without having to rebuild the container or manually change the configuration file each time the program is run. For example, in the previous section we set the `MASKCAM_DEVICE_ADDRESS` variable to indicate our Nano's IP address. A list of configurable parameters is shown in [maskcam_config.txt](maskcam_config.txt). The mapping between environment variable names and configuration parameters is defined in [maskcam/config.py](maskcam/config.py).

This section shows how to set environment variables to change configuration parameters. For example, if you want to use the `/dev/video1` camera device rather than `/dev/video0`, you can define `MASKCAM_INPUT` when running the container:

```
# Run with MASKCAM_INPUT and MASKCAM_DEVICE_ADDRESS
sudo docker run --runtime nvidia --privileged --rm -it --env MASKCAM_INPUT=v4l2:///dev/video1 --env MASKCAM_DEVICE_ADDRESS=<your-jetson-ip> -p 1883:1883 -p 8080:8080 -p 8554:8554 maskcam/maskcam-beta
```

As another example, if you have an already set up a MQTT server (as shown in [MQTT Server Setup section](#mqtt-server-setup)), you need to define
two addtional environment variables, `MQTT_BROKER_IP` and `MQTT_DEVICE_NAME`. This allows your device to find the MQTT server and identify itself:

```
# Run with MQTT_BROKER_IP, MQTT_DEVICE_NAME, and MASKCAM_DEVICE_ADDRESS
sudo docker run --runtime nvidia --privileged --rm -it --env MQTT_BROKER_IP=<server IP> --env MQTT_DEVICE_NAME=<a-unique-string-you-like> --env MASKCAM_DEVICE_ADDRESS=<your-jetson-ip> -p 1883:1883 -p 8080:8080 -p 8554:8554 maskcam/maskcam-beta
```

*If you have too many `--env` variables to add, it might be easier to create a [.env file](https://docs.docker.com/compose/env-file/) and point to it using the `--env-file` flag instead.*

### Troubleshooting
MaskCam actually consists of many different processes running in parallel. As a consequence, when there's an error on a particular process, all of them will be sent termination signals and finish gracefully. This means that you need to scroll up through the output to find out the original error that caused a failure. It should be very notorious, flagged as a red **ERROR** log entry, followed by the name of the process that failed and a message.

#### Error: camera not connected/not recognized
If you see an error containing the message `Cannot identify device '/dev/video0'`, among other Gst and v4l information, it means the program couldn't find the camera device. Make sure your camera is connected to the Nano and recognized by the host Ubuntu OS by issuing `ls /dev` and checking if `/dev/video0` is present in the output.

#### Error: not running in privileged mode
In this case, you'll see a bunch of annoying messages like:
```
Error: Can't initialize nvrm channel
Couldn't create ddkvic Session: Cannot allocate memory
nvbuf_utils: Could not create Default NvBufferSession
```
You'll probably see multiple failures in other MaskCam processes as well. To resolve these errors, make sure you're running docker with the `--privileged` flag, as described in the [first section](#running-maskcam-from-a-container-on-a-jetson-nano-developer-kit).

#### Error: reason not negotiated/camera capabilities
If you get an error that looks like: `v4l-camera-source / reason not-negotiated`
Then the problem is that the USB camera you're using doesn't support the default `camera-framerate=30` (frames per second). If you don't have another camera, try running the script under utils/gst_capabilities.sh and find the lines with type `video/x-raw ...`

Find any suitable `framerate=X/1` (with `X` being an integer like 24, 15, etc.) and set the corresponding configuration parameter with `--env MASKCAM_CAMERA_FRAMERATE=X` (see [previous section](#setting-device-configuration-parameters)).

#### Error: Streaming or file server are not accessible (nothing else seems to fail)
Make sure you're mapping the right ports from the container, with the `-p container_port:host_port` parameters indicated in the previous sections. The default port numbers, that should be exposed by the container, are configured in [maskcam_config.txt](maskcam_config.txt) as:
```
fileserver-port=8080
streaming-port=8554
mqtt-broker-port=1883
```
These port mappings are why we use `docker run ...  -p 1883:1883 -p 8080:8080 -p 8554:8554 ...` with the run command. Remember that all the ports can be overriden using environment variables, as described in the [previous section](#setting-device-configuration-parameters). Other ports like `udp-port-*` are not intended to be accessible from outside the container, they are used for communication between the inference process and the streaming and file-saving processes.

#### Other Errors
Sometimes after restarting the process or the whole docker container many times, some GPU resources can get stuck and cause unexpected errors. If that's the case, try rebooting the device and running the container again. If you find that the container fails systematically after running some sequence, please don't hesitate to report an Issue with the relevant context and we'll try to reproduce and fix it.

## MQTT Server Setup
### Running the MQTT Broker and Web Server
MaskCam is intended to be set up with a web server that stores mask detection statistics and allows users to remotely interact with the device. We've created a server [(maskcam/server)](maskcam/server) that receives statistics from the device, stores them in a database, and has a web-based GUI frontend to display them. A screenshot of the frontend for an example device is shown below.

*Insert frontend screenshot here*

You can test out and explore this functionality by building a server on another PC on your local network and pointing your Jetson Nano MaskCam device to it. This section gives instructions on how to do so. The MQTT broker and web server can be built and run on a Linux or OSX machine; we've tested it on Ubuntu 18.04LTS and OSX Big Sur.

The server consists of a couple docker containers, that run together using [docker-compose](https://docs.docker.com/compose/install/). Install docker-compose on your machine by following the [installation instructions for your platform](https://docs.docker.com/compose/install/) before continuing. All other necessary packages and libraries will be automatically installed when you set up the containers in the next steps.

After installing docker-compose, clone this repo:
```
git clone https://github.com/bdtinc/maskcam.git
```

Go to the `server/` folder, which has a complete implementation of the server in four different containers: the Mosquitto broker, backend API, database, and Streamlit frontend.

These containers are configured using environment variables, create the `.env` files by copying the default templates:
```
cd server
cp database.env.template database.env
cp frontend.env.template frontend.env
cp backend.env.template backend.env
```

The only file that needs to be changed is `database.env`. Open it with a text editor and replace the `<DATABASE_USER>`, `<DATABASE_PASSWORD>`, and `<DATABASE_NAME>` fields with your own values. Here are some example values, but you better be more creative for security reasons:
```
POSTGRES_USER=postgres
POSTGRES_PASSWORD=some_password
POSTGRES_DB=maskcam
```

*NOTE:* If you want to change any of the `database.env` values after building the containers, the easiest thing to do is to delete the `pgdata` volume by running `docker volume rm pgdata`. It will also delete all stored database information and statistics.

After editing the database environment file, you're ready to build all the containers and run them in a single command:

```
docker-compose up -d
```

Wait a couple minutes after issuing the command to make sure that all containers are built and running. Then, check the IP of the new docker server by issuing `ifconfig` and finding the IP of the `docker0` interface. (Typically, it looks something like `172.17.0.1`.)

Next, open a web browser and enter the server IP to visit the frontend webpage:
```
http://<server IP>:8501/
```
If you see a `ConnectionError` in the frontend, wait a couple more minutes and reload the page. The backend container can take some time to finish the database setup.

*NOTE:* If you're setting the server up on a remote instance like an AWS EC2, make sure you have ports `1883` and `8501` open for inbound and outbound traffic.


### Setup a device with your server

After configuring the server (locally or in an AWS EC2 instance with public IP),
and making sure that port `1883` of your server is accessible for inbound and
outbound traffic, and from your Jetson Device (see [next section](#checking-mqtt-connection) in case of trouble),
you just need to set the server IP and a name on your device:

```
# Run with MQTT_BROKER_IP, MQTT_DEVICE_NAME, and MASKCAM_DEVICE_ADDRESS
docker run --runtime nvidia --privileged --rm -it --env MQTT_BROKER_IP=<server IP> --env MQTT_DEVICE_NAME=my-jetson-1 --env MASKCAM_DEVICE_ADDRESS=<your-jetson-ip> -p 1883:1883 -p 8080:8080 -p 8554:8554 maskcam/maskcam-beta
```

And that's it. If the device has access to the broker's IP, then you should see in the output logs some successful connection messages and then see your device listed
in the drop-down menu of the frontend (reload the page if you don't see it). In the frontend, select `Group data by: Second` and hit `Refresh status` to see how the plot changes when new data arrives.

Check the next section if the MQTT connection is not established.

### Checking MQTT connection
If you're running the MQTT broker on a machine in your local network, make sure it's IP is accessible from the jetson device:
```
ping <local server IP>
```

If you're setting up a remote server and using it's public IP to connect
from your device, chances are you're not setting properly the port `1883` to be opened for inbound and outbound traffic.
If you want to check the port is correctly configured, use `netstat` from a local machine or your jetson:
```
nc -vz <server IP> 1883
```
Remember you also need to open port `8501` to access the web server frontend from a web browser, as explained in the [server configuration section](#running-the-mqtt-broker-and-web-server) (but that's not relevant for the MQTT communication with the device).

## Accessing the MaskCam container
### Development mode: manually running MaskCam
If you want to play around with the code, you probably don't want the container to automatically start running the `maskcam_run.py` script.
The easiest way to achieve that, is by defining the environment variable `DEV_MODE=1`:
```
docker run --runtime nvidia --privileged --rm -it --env DEV_MODE=1 -p 1883:1883 -p 8080:8080 -p 8554:8554 maskcam/maskcam-beta
```
This will cause the container to start a `/bin/bash` prompt (see [docker/start.sh](docker/start.sh) for details), from which you could run the script manually, or any
of its sub-modules as standalone processes:

```
# e.g: Run with a different input instead of default `/dev/video0`
./maskcam_run.py v4l2:///dev/video1

# e.g: Disable tracker to visualize raw detections and scores
MASKCAM_DISABLE_TRACKER=1 ./maskcam_run.py
```

### Debugging: running MaskCam modules as standalone processes
Actually, the script `maskcam_run.py`, which is the main entrypoint for the MaskCam software, has two roles:
 - Handles all the MQTT communication (send stats and receive commands)
 - Orchestrates all other processes that live under `maskcam/maskcam_*.py`.

But you can actually run any of those modules as standalone processes, which might be easier to debug some errors.

You need to set `DEV_MODE=1` as explained in the previous section to access the container prompt, and then you can run the python modules:

```
# e.g: Run only the static file server process
python3 -m maskcam.maskcam_fileserver
# e.g: Serve another directory to test
python3 -m maskcam.maskcam_fileserver /tmp

# e.g: Run only the inference and streaming processes
python3 -m maskcam.maskcam_streaming &
# Hit enter until you get a prompt and then:
python3 -m maskcam.maskcam_inference
```

**Note:** In the last example, `maskcam_streaming` is running on background,
so it will not terminate if you press `Ctrl+C` (only `maskcam_inference` will,
since it's running on the foreground).

To check that the streaming is still running and then bring it to foreground to terminate it, run:
```
jobs
fg %1
# Now you can hit Ctrl+C to terminate streaming
```

## Building from Source on Jetson Nano Developer Kit
The easiest way to get Maskcam running or set up for development purposes, is by using a container like the one provided in the main [Dockerfile](Dockerfile), which provides the right versions of the OS (Ubuntu 18.04 / Bionic Beaver) and all the system level packages required (mainly NVIDIA L4T packages, GStreamer and DeepStream among others).

For development, you could make modifications to the code or the container definition, and then rebuild locally using:
```
docker build . -t maskcam_custom
```

The above building step could be executed in the target Jetson Nano device (easier), or in another development environment (i.e: pushing the result to [Docker Hub](https://hub.docker.com/) and then pulling from device).

Either way, once the image is ready on the device, remember to run the container using the `--runtime nvidia` and `--privileged` flags (to access the camera device), and mapping the used ports (MQTT -1883-, static file serving -8080- and streaming -8554-, as defined in [maskcam_config.txt](maskcam_config.txt)):
```
docker run --runtime nvidia --privileged --rm -it -p 1883:1883 -p 8080:8080 -p 8554:8554 maskcam_custom
```

If you still want to better understand some of the [Dockerfile](Dockerfile) steps, or you need to run without a container and are willing to deal with version conflicts, please see the dependencies manual installation and building instructions at [docs/Manual-Dependency-Installation.md](docs/Manual-Dependencies-Installation.md)

## Running on Jetson Nano Developer Kit using balenaOS

balenaOS is a very light weight distribution designed for running containers on edge devices which when combined with Balena's balenaCloud mangament system has a number of advantages for fleet deployment and management. Explaining the details of how to set up balenaCloud applications is beyond the scope of this document, but you can test MaskCam on balenaOS using a local development environment setup. Except for installing balenaOS and using a slightly modified launch command, this process is essentially the same as the Jetson Nano Development kit instructions above.
This will require a Jetson Nano Development Kit, a 32 gb or higher micro-sd card, and another computer (referred to here as main system) on the same network.

### Installing balenaOS
First, go to https://www.balena.io/os/?, scroll down and download the development version for Nvidia Jetson Nano SD-CARD.

Next, go to https://www.balena.io/etcher/ and install balenaEtcher.

In balenaEtcher, simply select the zip file you downloaded, and after inserting the sd card into your main system select it, then press the 'Flash!' icon.

After the flashing process is completed, place the sd card into your Jetson Nano Development Kit, ensure the network cable is plugged into the device and power up the Jetson.

### Installing balena CLI

Use the instructions here https://github.com/balena-io/balena-cli/blob/master/INSTALL.md to install the balena CLI tool.

### Connecting to your Jetson

First, in a terminal on your main system run the command:
```
sudo balena scan
```
Note the ip address in the result.

Next connect to your Jetson:
```
balena ssh balena.local
```

At this point you are in a console as root user on your Jetson running balenaOS. The commands from this point on are exactly the same as the instructions for running using JetPack on the Nano Developer Kit with the following differences.
1. The `docker` command is replaced by `balena`
2. Do not use the `--runtime nvidia` switch. It is automatic on balenaOS for Jetson and you will get errors if you include it.

So issuing the following commands will run MaskCam:
```
$ balena pull maskcam/maskcam-beta

$ balena run --privileged --rm -it --env MASKCAM_DEVICE_ADDRESS=10.0.0.245 -p 1883:1883 -p 8080:8080 -p 8554:8554 maskcam/maskcam-beta
```

Note that building from source is significantly different on balenaOS than using docker under JetPack. If you wish to do this, you should familarize yourself with the details of balenaOS and also consider using balenaCloud (which has free accounts for under 10 devices).

## Running on Jetson Nano with Photon carrier board
Please see the setup instructions at [docs/Photon-Nano-Setup.md](docs/Photon-Nano-Setup.md) for how to set up and run MaskCam on the Photon Nano.

## Useful development scripts
During development, some scripts were produced which might be useful for
other developers to debug or update the software. These include an MQTT sniffer,
a script to run the TensorRT model on images, and to convert a model trained
with the original YOLO Darknet implementation to TensorRT.

Basic usage for all these tools is covered on [docs/Useful-Development-Scripts.md](docs/Useful-Development-Scripts.md).

# MaskCam <!-- omit in toc -->

<p align="center">
  <img src="/docs/imgs/MaskCam-Demo1.gif">
</p>

MaskCam is a prototype reference design for a Jetson Nano-based smart camera system that measures crowd face mask usage in real-time, with all AI computation performed at the edge. MaskCam detects and tracks people in its field of view and determines whether they are wearing a mask via an object detection, tracking, and voting algorithm. It uploads statistics (not videos) to the cloud, where a web GUI can be used to monitor face mask compliance in the field of view. It saves interesting video snippets to local disk (e.g., a sudden influx of lots of people not wearing masks) and can optionally stream video via RTSP.

MaskCam can be run on a Jetson Nano Developer Kit, or on a Jetson Nano module (SOM) with the ConnectTech Photon carrier board. It was designed to use the Raspberry Pi High Quality Camera but will also work with pretty much any USB webcam that is supported on Linux.

The on-device software stack is mostly written in Python and runs under JetPack 4.4.1 or 4.5. Edge AI processing is handled by NVIDIA’s DeepStream video analytics framework, YOLOv4-tiny, and Tryolabs' [Norfair](https://github.com/tryolabs/norfair) tracker.  MaskCam reports statistics to and receives commands from the cloud using MQTT and a web-based GUI. The software is containerized and for evaluation can be easily installed on a Jetson Nano DevKit using docker with just a couple of commands. For production, MaskCam can run under balenaOS, which makes it easy to manage and deploy multiple devices.

We urge you to try it out! It’s easy to install on a Jetson Nano Developer Kit and requires only a web cam. (The cloud-based statistics server and web GUI are optional, but are also dockerized and easy to install on any reasonable Linux system.)  [See below for installation instructions.](#running-maskcam-from-a-container-on-a-jetson-nano-developer-kit)

MaskCam was developed by Berkeley Design Technology, Inc. (BDTI) and Tryolabs S.A., with development funded by NVIDIA. MaskCam is offered under the MIT License. For more information about MaskCam, please see the [report from BDTI](https://www.bdti.com/maskcam). If you have questions, please email us at maskcam@bdti.com. Thanks!

## Table of contents <!-- omit in toc -->
- [Start Here!](#start-here)
  - [Running MaskCam from a Container on a Jetson Nano Developer Kit](#running-maskcam-from-a-container-on-a-jetson-nano-developer-kit)
  - [Viewing the Live Video Stream](#viewing-the-live-video-stream)
  - [Setting Device Configuration Parameters](#setting-device-configuration-parameters)
- [MQTT Server Setup](#mqtt-and-web-server-setup)
  - [Running the MQTT Broker and Web Server](#running-the-mqtt-broker-and-web-server)
  - [Setup a Device with Your Server](#setup-a-device-with-your-server)
  - [Checking MQTT Connection](#checking-mqtt-connection)
- [Working With the MaskCam Container](#working-with-the-maskcam-container)
  - [Development Mode: Manually Running MaskCam](#development-mode-manually-running-maskcam)
  - [Debugging: Running MaskCam Modules as Standalone Processes](#debugging-running-maskcam-modules-as-standalone-processes)
- [Additional Information](#additional-information)
  - [Running on Jetson Nano Developer Kit Using BalenaOS](#running-on-jetson-nano-developer-kit-using-balenaos)
  - [Custom Container Development](#custom-container-development)
    - [Building From Source on Jetson Nano Developer Kit](#building-from-source-on-jetson-nano-developer-kit)
    - [Using Your Own Detection Model](#using-your-own-detection-model)
  - [Installing MaskCam Manually (Without a Container)](#installing-maskcam-manually-without-a-container)
  - [Running on Jetson Nano with Photon Carrier Board](#running-on-jetson-nano-with-photon-carrier-board)
  - [Useful Development Scripts](#useful-development-scripts)
- [Troubleshooting Common Errors](#troubleshooting-common-errors)


## Start Here!
### Running MaskCam from a Container on a Jetson Nano Developer Kit
The easiest and fastest way to get MaskCam running on your Jetson Nano Dev Kit is using our pre-built containers.  You will need:

1. A Jetson Nano Dev Kit running JetPack 4.4.1 or 4.5
2. An external DC 5 volt, 4 amp power supply connected through the Dev Kit's barrel jack connector (J25). (See [these instructions](https://www.jetsonhacks.com/2019/04/10/jetson-nano-use-more-power/) on how to enable barrel jack power.) This software makes full use of the GPU, so it will not run with USB power.
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

The MaskCam container should start running the `maskcam_run.py` script, using the USB camera as the default input device (`/dev/video0`). It will produce various status output messages (and error messages, if it encounters problems). If there are errors, the process will automatically end after several seconds. Check the [Troubleshooting](#troubleshooting-common-errors) section for tips on resolving errors.

Otherwise, after 30 seconds or so, it should continually generate status messages (such as `Processed 100 frames...`). Leave it running (don't press `Ctrl+C`, but be aware that the device will start heating up) and continue to the next section to visualize the video!

### Viewing the Live Video Stream
If you scroll through the logs and don't see any errors, you should find a message like:

```Streaming at rtsp://aaa.bbb.ccc.ddd:8554/maskcam```

where `aaa.bbb.ccc.ddd` is the address that you provided in `MASKCAM_DEVICE_ADDRESS` previously. If you didn't provide an address, you'll see some unknown address label there, but the streaming will still work.

You can copy-paste that URL into your RSTP streaming viewer ([see how](https://user-images.githubusercontent.com/12506292/111346333-e14d8800-865c-11eb-9242-0ffa4f50547f.mp4) to do it with VLC) on another computer. If all goes well, you should be rewarded with streaming video of your Nano, with green boxes around faces wearing masks and red boxes around faces not wearing masks. An example video of the live streaming in action is shown below.

<p align="center">
  <img src="/docs/imgs/MaskCam-Live1.gif">
</p>

This video stream gives a general demonstration of how MaskCam works. However, MaskCam also has other features, such as the ability to send mask detection statistics to the cloud and view them through a web browser. If you'd like to see these features in action, you'll need to set up an MQTT server, which is covered in the [MQTT Server Setup section](#mqtt-and-web-server-setup).

If you encounter any errors running the live stream, check the [Troubleshooting](#troubleshooting-common-errors) section for tips on resolving errors.

### Setting Device Configuration Parameters
MaskCam uses environment variables to configure parameters without having to rebuild the container or manually change the configuration file each time the program is run. For example, in the previous section we set the `MASKCAM_DEVICE_ADDRESS` variable to indicate our Nano's IP address. A list of configurable parameters is shown in [maskcam_config.txt](maskcam_config.txt). The mapping between environment variable names and configuration parameters is defined in [maskcam/config.py](maskcam/config.py).

This section shows how to set environment variables to change configuration parameters. For example, if you want to use the `/dev/video1` camera device rather than `/dev/video0`, you can define `MASKCAM_INPUT` when running the container:

```
# Run with MASKCAM_INPUT and MASKCAM_DEVICE_ADDRESS
sudo docker run --runtime nvidia --privileged --rm -it --env MASKCAM_INPUT=v4l2:///dev/video1 --env MASKCAM_DEVICE_ADDRESS=<your-jetson-ip> -p 1883:1883 -p 8080:8080 -p 8554:8554 maskcam/maskcam-beta
```

Another useful input device that you might want to use is a CSI camera (like the Raspberry Pi camera), and in that case you need to set `MASKCAM_INPUT=argus://0` instead of the value shown above.

As another example, if you have an already set up our MQTT and web server (as shown in [MQTT Server Setup section](#mqtt-and-web-server-setup)), you need to define
two addtional environment variables, `MQTT_BROKER_IP` and `MQTT_DEVICE_NAME`. This allows your device to find the MQTT server and identify itself:

```
# Run with MQTT_BROKER_IP, MQTT_DEVICE_NAME, and MASKCAM_DEVICE_ADDRESS
sudo docker run --runtime nvidia --privileged --rm -it --env MQTT_BROKER_IP=<server IP> --env MQTT_DEVICE_NAME=<a-unique-string-you-like> --env MASKCAM_DEVICE_ADDRESS=<your-jetson-ip> -p 1883:1883 -p 8080:8080 -p 8554:8554 maskcam/maskcam-beta
```

*If you have too many `--env` variables to add, it might be easier to create a [.env file](https://docs.docker.com/compose/env-file/) and point to it using the `--env-file` flag instead.*


## MQTT and Web Server Setup
### Running the MQTT Broker and Web Server
MaskCam is intended to be set up with a web server that stores mask detection statistics and allows users to remotely interact with the device. We wrote code for instantiating a [server](server/) that receives statistics from the device, stores them in a database, and has a web-based GUI frontend to display them. A screenshot of the frontend for an example device is shown below.

<p align="center">
  <img src="/docs/imgs/maskcam-frontend.PNG">
</p>

You can test out and explore this functionality by starting the server on a PC on your local network and pointing your Jetson Nano MaskCam device to it. This section gives instructions on how to do so. The MQTT broker and web server can be built and run on a Linux or OSX machine; we've tested it on Ubuntu 18.04LTS and OSX Big Sur. It can also be set up in an online AWS EC2 instance if you want to access it from outside of your local network.

The server consists of several docker containers that run together using [docker-compose](https://docs.docker.com/compose/install/). Install docker-compose on your machine by following the [installation instructions for your platform](https://docs.docker.com/compose/install/) before continuing. All other necessary packages and libraries will be automatically installed when you set up the containers in the next steps.

After installing docker-compose, clone this repo:
```
git clone https://github.com/bdtinc/maskcam.git
```

Go to the `server/` folder, which has all the needed components implemented on four containers: the Mosquitto broker, backend API, database, and Streamlit frontend.

These containers are configured using environment variables, so create the `.env` files by copying the default templates:
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

After editing the database environment file, you're ready to build all the containers and run them with a single command:

```
sudo docker-compose up -d
```

Wait a couple minutes after issuing the command to make sure that all containers are built and running. Then, check the local IP of your computer by running the `ifconfig` command. (It should be an address that starts with `192.168...`, `10...` or `172...`.) This is the server IP that will be used for connecting to the server (since the server is hosted on this computer).

Next, open a web browser and enter the server IP to visit the frontend webpage:
```
http://<server IP>:8501/
```
If you see a `ConnectionError` in the frontend, wait a couple more seconds and reload the page. The backend container can take some time to finish the database setup.

*NOTE:* If you're setting the server up on a remote instance like an AWS EC2, make sure you have ports `1883` (MQTT) and `8501` (web frontend) open for inbound and outbound traffic.


### Setup a Device With Your Server
Once you've got the server set up on a local machine (or in a AWS EC2 instance with a public IP), switch back to the Jetson Nano device. Run the MaskCam container using the following command, where `MQTT_BROKER_IP` is set to the IP of your server. (If you're using an AWS EC2 server, make sure to configure port `1883` for inbound and outbound traffic before running this command.)

```
# Run with MQTT_BROKER_IP, MQTT_DEVICE_NAME, and MASKCAM_DEVICE_ADDRESS
sudo docker run --runtime nvidia --privileged --rm -it --env MQTT_BROKER_IP=<server IP> --env MQTT_DEVICE_NAME=my-jetson-1 --env MASKCAM_DEVICE_ADDRESS=<your-jetson-ip> -p 1883:1883 -p 8080:8080 -p 8554:8554 maskcam/maskcam-beta
```

And that's it. If the device has access to the server's IP, then you should see in the output logs some successful connection messages and then see your device listed in the drop-down menu of the frontend (reload the page if you don't see it). In the frontend, select `Group data by: Second` and hit `Refresh status` to see how the plot changes when new data arrives.

Check the next section if the MQTT connection is not established from the device to the server.

### Checking MQTT Connection
If you're running the MQTT broker on a machine in your local network, make sure its IP is accessible from the Jetson device:
```
ping <local server IP>
```

*NOTE:* Remember to use the network address of the computer you set up the server on, which you can check using the `ifconfig` command and looking for an address that should start with `192.168...`, `10...` or `172...`

If you're setting up a remote server and using its public IP to connect
from your device, chances are you're not setting properly the port `1883` to be opened for inbound and outbound traffic.
If you want to check the port is correctly configured, use `nc` from a local machine or your jetson:
```
nc -vz <server IP> 1883
```
Remember you also need to open port `8501` to access the web server frontend from a web browser, as explained in the [server configuration section](#running-the-mqtt-broker-and-web-server) (but that's not relevant for the MQTT communication with the device).




## Working With the MaskCam Container
### Development Mode: Manually Running MaskCam
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

### Debugging: Running MaskCam Modules as Standalone Processes
The script `maskcam_run.py`, which is the main entrypoint for the MaskCam software, has two roles:
 - Handles all the MQTT communication (send stats and receive commands)
 - Orchestrates all other processes that live under `maskcam/maskcam_*.py`.

But you can actually run any of those modules as standalone processes, which can be easier for debugging.

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

## Additional Information
Further information about working with and customizing MaskCam is provided on separate pages in the [docs](docs) folder. This section gives a brief description and link to each page.

### Running on Jetson Nano Developer Kit Using BalenaOS
[BalenaOS](https://www.balena.io/os/) is a lightweight operating system designed for running containers on embedded devices. It provides several advantages for fleet deployment and management, especially when combined with balena's balenaCloud mangament system. If you'd like to try running MaskCam with balenaOS instead of JetPack OS on your Jetson Nano, please follow the instructions at [BalenaOS-DevKit-Nano-Setup.md](docs/BalenaOS-DevKit-Nano-Setup.md).

### Custom Container Development
MaskCam is intended to be a reference design for any connected smart camera application. You can create your own application by starting from our pre-built container, modifying it to add the code files and packages needed for your program, and then re-building the container. The [Custom-Container-Development.md](docs/Custom-Container-Development.md) gives instructions on how to build your own container based off MaskCam.

#### Building From Source on Jetson Nano Developer Kit
Please see [How to Build your Own Container from Source on the Jetson Nano](https://github.com/bdtinc/maskcam/blob/main/docs/Custom-Container-Development.md#how-to-build-your-own-container-from-source-on-the-jetson-nano) for instructions on how to build a custom MaskCam container on your Jetson Nano Developer Kit.

#### Using Your Own Detection Model
Please see [How to Use Your Own Detection Model](https://github.com/bdtinc/maskcam/blob/main/docs/Custom-Container-Development.md#how-to-use-your-own-detection-model) for instructions on how to use your own detection model rather than our mask detection model.

### Installing MaskCam Manually (Without a Container)
MaskCam can also be installed manually, rather than by downloading our pre-built container. Using a manual installation of MaskCam can help with development if you'd prefer not to work with containers. If you'd like to install MaskCam without using containers, please see [docs/Manual-Dependencies-Installation.md](docs/Manual-Dependencies-Installation.md).

### Running on Jetson Nano with Photon Carrier Board
For our hardware prototype of MaskCam, we used a Jetson Nano module and a [Connect Tech Photon carrier board](https://connecttech.com/product/photon-jetson-nano-ai-camera-platform/), rather than the Jetson Nano Developer Kit. We used the Photon because the Developer Kit is not sold or warrantied for production use. Using the Photon allowed us to quickly create a production-ready prototype using off-the-shelf hardware. If you have a Photon carrier board and Jetson Nano module, you can install MaskCam on them by using the setup instructions at [docs/Photon-Nano-Setup.md](docs/Photon-Nano-Setup.md).

### Useful Development Scripts
During development, some scripts were produced which might be useful for other developers to debug or update the software. These include an MQTT sniffer, a script to run the TensorRT model on images, and to convert a model trained with the original YOLO Darknet implementation to TensorRT format. Basic usage for all these tools is covered on [docs/Useful-Development-Scripts.md](docs/Useful-Development-Scripts.md).


## Troubleshooting Common Errors
If you run into any errors or issues while working with MaskCam, this section gives common errors and their solutions. 

MaskCam consists of many different processes running in parallel. As a consequence, when there's an error on a particular process, all of them will be sent termination signals and finish gracefully. This means that you need to scroll up through the output to find out the original error that caused a failure. It should be very notorious, flagged as a red **ERROR** log entry, followed by the name of the process that failed and a message.

#### Error: camera not connected/not recognized
If you see an error containing the message `Cannot identify device '/dev/video0'`, among other Gst and v4l messages, it means the program couldn't find the camera device. Make sure your camera is connected to the Nano and recognized by the host Ubuntu OS by issuing `ls /dev` and checking if `/dev/video0` is present in the output.

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
Sometimes after restarting the process or the whole docker container many times, some GPU resources can get stuck and cause unexpected errors. If that's the case, try rebooting the device and running the container again. If you find that the container fails systematically after running some sequence, please don't hesitate to [report an Issue](https://github.com/bdtinc/maskcam/issues) with the relevant context and we'll try to reproduce and fix it.

## Questions? Need Help?
Email us at maskcam@bdti.com, and be sure to check out our [independent report on the development of MaskCam](https://bdti.com/maskcam)!


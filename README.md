# MaskCam
MaskCam is a reference design for a Jetson Nano-based smart camera system that measures crowd face mask usage in real-time, with all AI computation performed at the edge. MaskCam detects and tracks people in its field of view and determines whether they are wearing a mask via an object detection, tracking, and voting algorithm. It uploads statistics (not videos) to the cloud, where a web GUI can be used to monitor the face mask compliance in the field of view. It saves interesting video snippets to local disk (e.g., a sudden influx of lots of people not wearing masks) and can optionally stream video via RTSP.

MaskCam can be run on a Jetson Nano Developer Kit, or on a Jetson Nano SOM with the ConnectTech Photon carrier board.  It was designed to use the Raspberry Pi High Quality Camera but will also work with pretty much any USB webcam.

The on-device software stack is mostly written in Python and runs under JetPack 4.4.1 or 4.5. Edge AI processing is handled by Nvidia’s DeepStream video analytics framework and YoloV4 Tiny, and Tryolab's Norfair tracker.  MaskCam reports statistics to and receives commands from the cloud using MQTT and a web-based GUI. The software is containerized and for evaluation can be easily installed on a Jetson Nano DevKit using docker with just a couple of commands. For production, MaskCam can run under BalenaOS, which makes it easy to manage and deploy multiple devices.

We urge you to try it out! It’s easy to install on a Jetson Nano Dev Kit and requires only a web cam. (The cloud-based statistics server and web GUI are optional, but are also dockerized and easy to install on any reasonable Linux system.)  [See below for installation instructions.](https://github.com/tryolabs/bdti-jetson#start-here-running-maskcam-from-a-container-on-a-jetson-nano-developer-kit)

MaskCam was developed by Berkeley Design Technology, Inc. (BDTI) and Tryolabs S.A., with development funded by Nvidia. MaskCam is offered under the MIT License. For more information about MaskCam, please see the forthcoming white paper from BDTI.

## Start Here! Running MaskCam from a Container on a Jetson Nano Developer Kit
The easiest and fastest way to get MaskCam running on your Jetson Nano Dev Kit is using our pre-built containers.  You will need:

1. A Jetson Nano Dev Kit running JetPack 4.4.1 or 4.5
2. The external DC 4A power supply. This software makes full use of the GPU so it will not run with USB power.
3. A USB webcam or RasPi HQ camera attached to your Nano
4. Another computer with a program that can display RTSP streams -- we suggest VLC or QuickTime.

On your Nano, run:
```
docker pull maskcam/maskcam-beta
```
Note that the container is quite large, so it will take maybe 10 minutes to download and install.

Next, make sure that the 4A external power supply is connected and run:
```
docker run --runtime nvidia --privileged --rm -it -p 1883:1883 -p 8080:8080 -p 8554:8554 maskcam/maskcam-beta
```

The container should start running the `maskcam_run.py` script with the default input device (`/dev/video0`).

MaskCam will produce a whole bunch of status output (and error messages, if it encounters problems).
If there are errors, the process will finish after a couple seconds (check [Troubleshooting](Troubleshooting)).

If you don't see any errors, you can run your RSTP streaming viewer (e.g., VLC) on another computer and point it to:
```
rtsp://aaa.bbb.ccc.ddd:8554/maskcam
```

where aaa.bbb.ccc.ddd is the IP address of your Nano. 
**NOTE:** if you scroll up through the MaskCam output, you should see a message like `Streaming at rtsp://192.168.0.2:8554/maskcam`,
which you can copy-paste as the network URL, as long as you're in the same network that your device.

If all goes well, you should be rewarded with streaming video of your Nano, with green boxes around faces wearing masks and red boxes around faces not wearing masks.

This mode just gives an idea of how MaskCam works.  But it's not sending any statistics to the cloud, since we haven't enabled that yet.  If you want to play with that, you'll need to set up an MQTT server, which is covered in the next sections.

### Running manually (avoiding auto-start)
If you want to play around with the code and configuration parameters, you probably don't want the container to automatically start running the `maskcam_run.py` script.
The easiest way to achieve that, is by defining the environment variable `DEV_MODE=1`:
```
docker run --runtime nvidia --privileged --rm -it --env DEV_MODE=1 -p 1883:1883 -p 8080:8080 -p 8554:8554 maskcam/maskcam-beta
```
This will cause the container to start a `/bin/bash` prompt (see [docker/start.sh](docker/start.sh) for details), from which you could run the script manually, or any
of its sub-modules as standalone processes:

```
# Run with a different input instead of default `/dev/video0`
./maskcam_run.py v4l2:///dev/video1

# Disable tracker to visualize raw detections and scores (see next section for more options)
MASKCAM_DISABLE_TRACKER=1 ./maskcam_run.py

# For debugging purposes, you could instead run any of the maskcam/maskcam_*.py modules as standalone processes

# Run only the static file server process (not very useful until you have a file on `fileserver-hdd-dir=/tmp/saved_videos`)
python3 -m maskcam.maskcam_fileserver

# Run only the inference process (not very useful without the streaming or filesave processes running in parallel, but maybe useful for debugging)
python3 -m maskcam.maskcam_inference
```


### Setting configuration parameters
The easiest way to configure parameters (without rebuilding the container or running manually and changing the config file each time), is through environment variables.
For example, if you want to set an input device other than `/dev/video0`, you can define `MASKCAM_INPUT`:

```
docker run --runtime nvidia --privileged --rm -it --env MASKCAM_INPUT=v4l2:///dev/video1 -p 1883:1883 -p 8080:8080 -p 8554:8554 maskcam/maskcam-beta
```

There are many other options that may be set using environment variables, which override the values written in the [maskcam_config.txt](maskcam_config.txt) file.

You might want to take a look at that configuration file for a brief comment on what they do, and then check the [maskcam/config.py](maskcam/config.py) file to see all
the names of the environment variables that can be used to override these values when running the container (instead of modifying the file in the container).

### Troubleshooting
MaskCam actually consists of many different processes running in parallel. As a consequence, when there's an error on a particular process, all of them will be sent termination signals
and finish gracefully. This means that you need to scroll up through the output to find out the original error that caused a failure. It should be very notorious, flagged as a red **ERROR** log entry, followed by the name of the process that failed and a message.

#### Error: camera not connected/not recognized
You should see an error containing the message `Cannot identify device '/dev/video0'`, among other Gst and v4l information.

Make sure the camera is connected and recognized by the host Ubuntu OS, where there should also be a device present `/dev/video0`.

#### Error: not running in privileged mode
In this case, you'll see a bunch of annoying messages like:
```
Error: Can't initialize nvrm channel
Couldn't create ddkvic Session: Cannot allocate memory
nvbuf_utils: Could not create Default NvBufferSession
```
Among other multiple failures on the MaskCam processes as well.

Make sure you're running docker with the `--privileged` flag, as described in the previous sections.

#### Error: reason not negotiated/camera capabilities
If the error is like: v4l-camera-source / reason not-negotiated
Then the problem is that the USB camera you're using doesn't support the default `camera-framerate=30` (frames per second).

If you don't have another camera, try running the script under utils/gst_capabilities.sh and find the lines with type
`video/x-raw ...`

Find any suitable `framerate=X/1` (with `X` being an integer like 24, 15, etc.)
and set the corresponding configuration parameter with `--env MASKCAM_CAMERA_FRAMERATE=X` (see [previous section](Setting-configuration-parameters)).

#### Error: Streaming or file server are not accessible (nothing else seems to fail)
Make sure you're mapping the right ports from the container, with the `-p container_port:host_port` parameters indicated in the previous sections.

The default port numbers, that should be exposed by the container, are configured in [maskcam_config.txt](maskcam_config.txt) as:
```
fileserver-port=8080
streaming-port=8554
mqtt-broker-port=1883
```
And that's why we're using `docker run ...  -p 1883:1883 -p 8080:8080 -p 8554:8554 ...` in the previous sections.

Remember that all these ports can be overriden using environment variables, as described in the [previous section](Setting-configuration-parameters).

Other ports like `udp-port-*` are not intended to be accessible from outside the container, they are used for communication between the inference process and the streaming and file-saving processes.

#### Other errors
Sometimes after restarting the process or the whole docker container many times, some GPU resources can get stuck and cause unexpected errors.

If that's the case, try rebooting the device and running the container again.

If you find that the container fails systematically after running some sequence, please don't hesitate
to report an Issue with the relevant context and we'll try to reproduce and fix it.

## Setting up and Running the MQTT Broker and Web Server
XXX Braulio, this needs to be fixed/updated/expanded.  My hacks are below.

The MQTT broker and web server can be run on a Linux or OSX machine; we've tested it on Ubuntu 18.04LTS and OSX XXXversionXXX.

XXX Braulio: does the server need to be run as root?
XXX Braulio: it looks like we need postgres installed, and we'll need to set up a postgres user?  I notice in the database.env file there is stuff like POSTGRES_USER=<DATABASE_USER>, POSTGRES_PASSWORD=<...>, POSTGRES_DB=<...>

On your server machine, if you don't have docker installed, you'll need to install it, as root:
```
XXX Braulio, commannds here
```

Then clone this repo:
```
git clone https://github.com/tryolabs/bdti-jetson    XXX update me!
```

Under the `server/` folder you'll find a complete implementation of a server using docker-compose,
which contains a mosquitto broker, backend API, database, and streamlit frontend.

Note that you can also run only the MQTT broker service to test the device (see section above).

To create all the services for the web application, create the `.env` files using the default templates:
```
cd server
cp database.env.template database.env
cp frontend.env.template frontend.env
cp backend.env.template backend.env

docker-compose build
docker-compose up
```

## Running on Jetson Nano with Photon carrier board
Please see the setup instructions at [docs/Photon-Nano-Setup.md](docs/Photon-Nano-Setup.md) for how to set up and run MaskCam on the Photon Nano.

## Developing and Building from Source on Jetson Nano Developer Kit
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

However, if you want to better understand the [Dockerfile](Dockerfile), or you need to run natively and are willing to deal with version conflicts, please see the dependencies manual installation and building instructions at [docs/Manual-Dependency-Installation.md](docs/Manual-Dependency-Installation.md)


### Sending MQTT Messages
*XXX Braulio, I think this should be moved to docs/Send-MQTT-Commands.md, no need for it here.*

If you just want to test MQTT messages and be able to send commands to the device, you might run
the MQTT broker in your local machine and set your IP as the `MQTT_BROKER_IP`.

The MQTT broker is called `mosquitto` and can be run locally if you have `docker-compose` in your computer:
```
cd server
cp database.env.template database.env
cp frontend.env.template frontend.env
cp backend.env.template backend.env

docker-compose up mosquitto
```

Then you can run the MQTT commander script for debugging on your local computer or from the Jetson device itself:
```
export MQTT_BROKER_IP=<server ip (local or remote)>
export MQTT_DEVICE_NAME=<device to command>
python3 -m maskcam.mqtt_commander
```

Note that you'll need to set the IP of the MQTT Broker as `127.0.0.1` if you're running the commander in the
same computer where you're running docker-compose, or set it to your computer's network address if running
on the device (same `MQTT_BROKER_IP` that you need to run `maskcam_run.py`).

### Running MaskCam Standalone Services
*XXX Braulio, I think this should be moved to docs/Running-MaskCam-Standalone-Services.md, no need for it here.*

When `maskcam_run.py` is run, it actually runs several processes which can be run individually:
```bash
# This process runs DeepStream and generates UDP video packages to be used in other processes
python3 -m maskcam.maskcam_inference
```

In another terminal, run simultaneously (this will start saving a file from UDP packages, until Ctrl+C is pressed):
```bash
python3 -m maskcam.maskcam_filesave
```

To visualize the stream remotely via RTSP, start the streaming service:
```bash
python3 -m maskcam.maskcam_streaming
```

The same concept applies to the static file server `maskcam_fileserver`.


## Running TensorRT engine on images
*XXX Braulio, I think this and the next section should be moved to docs/MaskCam-Neural-Network-Notes.md, no need for it here.  I also think it should have some discussion about Yolo vs. Mobilenet and what you would need to do if you want to swap out one object detector for another.*

After following the steps to run `maskcam` (except that you don't need DeepStream for this part),
you might also want to test the object detector on a folder with images:
```
cd yolo/
python3 run_yolo_images.py path/to/input/folder path/to/output/folder
```

## Convert weights generated using the original darknet implementation to TRT
 1. Clone the pytorch implementation of YOLOv4:
```
git clone git@github.com:Tianxiaomo/pytorch-YOLOv4.git
```
 2. Convert the Darknet model to ONNX using the script in `tool/darknet2onnx.py`, e.g:
```
PYTHONPATH='pytorch-YOLOv4:$PYTHONPATH' python3 pytorch-YOLOv4/tool/darknet2onnx.py yolo/facemask-yolov4-tiny.cfg yolo/facemask-yolov4-tiny_best.weights <optional batch size>
```
 3. Convert the ONNX model to TRT (on the Jetson Nano, `trtexec` can be found under `/usr/src/tensorrt/bin/trtexec`):
```
/usr/src/tensorrt/bin/trtexec --fp16 --onnx=../yolo/yolov4_1_3_608_608_static.onnx --explicitBatch --saveEngine=tensorrt_fp16.trt
```

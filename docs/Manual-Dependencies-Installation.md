## Manual installation and building of dependencies

These instructions are aimed to manually recreate a native environment similar to the one produced by the [Dockerfile](Dockerfile).

They are tested on **Ubuntu 18.04 (Bionic Beaver)** with **Jetpack 4.4.1**.

1. Make sure these packages are installed at system level (other required packages are not listed here since they're included with Jetpack, check the [Dockerfile](Dockerfile) for a complete list):
```
sudo apt install git, python3-pip, python3-opencv python3-libnvinfer python-gi-dev cuda-toolkit-10-2
```

2. Clone this repo:
```
git clone <copy https or ssh url>.git
```

3. Copy any `.egg-info` file under `docker/` to the python's `dist-packages` dir, so that system-level installed packages are visible by Pypi:
```
sudo cp docker/*.egg-info /usr/lib/python3/dist-packages/
```

4. Install the requirements listed on `requirements.txt`:
```
pip3 install -r requirements.txt
```

If any version above fails or you want to ignore the pinned versions for some reason, try:
```
# Only run this if you don't want to use the pinned versions
pip3 install -r requirements.in -c docker/constraints.docker
```

5. Install Nvidia DeepStream:
Aside from the system requirements of th previous step, you also need to install
[DeepStream 5.0](https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_Quickstart.html#jetson-setup) 
(no need to install Kafka protocol adaptor)
and also make sure to install the corresponding **python bindings** for GStreamer
[gst-python](https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_Python_Sample_Apps.html#python-bindings),
and for DeepStream [pyds](https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_Python_Sample_Apps.html#metadata-access).

6. Compile YOLOv4 plugin for DeepStream:
After installing DeepStream, compile the YOLOv4 plugin for DeepStream:
```
cd <this repo path>/deepstream_plugin_yolov4
export CUDA_VER=10.2
make
```
If all went well, you should see a library `libnvdsinfer_custom_impl_Yolo.so` in that directory.

7. Download TensorRT engine file from [here](https://maskcam.s3.us-east-2.amazonaws.com/facemask_y4tiny_1024_608_fp16.trt) and save it as `yolo/facemask_y4tiny_1024_608_fp16.trt`.

8. Now you should be ready to run. By default, the device `/dev/video0` will be used, but other devices can be set as first argument:
```bash
# Use default input camera /dev/video0
python3 maskcam_run.py

# Equivalent as above:
python3 maskcam_run.py v4l2:///dev/video0

# Process an mp4 file instead (no network functions, MQTT and static file server disabled)
python3 maskcam_run.py file:///path/to/video.mp4

# Read from Raspi2 camera using device-id
python3 maskcam_run.py argus:///0
```

Check the main [README.md](README) for more parameters that can be configured before running, using environment variables.

# MaskCam [BDTi Cube]
Adaptation of the Face Masks Detector to run on Jetson Nano

## Running on Jetson Nano with Photon carrier board
Please see the setup instructions at [Photon-Nano-Setup.md](https://github.com/tryolabs/bdti-jetson/blob/main/Photon-Nano-Setup.md) for how to set up and run MaskCam on the Photon Nano.

## Preparing to run on Jetson Nano Developer Kit
1. Make sure these packages are installed at system level:
```
sudo apt install python3-opencv python3-libnvinfer
```

2. Clone this repo and also `norfair` and `filterpy` at the same level:
```
git clone git@github.com:tryolabs/bdti-jetson.git

git clone git@github.com:tryolabs/norfair.git
git clone git@github.com:rlabbe/filterpy.git
```

3. Install the requirements listed on `requirements.in`:
```
pip3 install -r requirements.in
```

4. Run this and eventually add it to the `.bashrc` or `.profile` files:
```
export PYTHONPATH=../../norfair:../../filterpy 
```

## Running inference
### Using DeepStream (Jetson)
Aside from the system requirements of th previous section, you also need to install
[DeepStream 5.0](https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_Quickstart.html#jetson-setup) 
(no need to install Kafka protocol adaptor)
and also make sure to install the corresponding **python bindings** for GStreamer
[gst-python](https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_Python_Sample_Apps.html#python-bindings),
and for DeepStream [pyds](https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_Python_Sample_Apps.html#metadata-access).

After installing the requirements, compile the YOLOv4 plugin for DeepStream:
```
cd bdti-jetson/deepstream/plugin_yolov4/nvdsinfer_custom_impl_Yolo
export CUDA_VER=10.2
make
```
If all went well, you should see a library `libnvdsinfer_custom_impl_Yolo.so` in that directory.

Now you should be ready to process some video using DeepStream:
```
cd bdti-jetson/deepstream
python3 deepstream_facemask.py file:///home/<path to the video>
```


### Using only TensorRT for python
Run `run_yolo.py` (make sure you exported $PYTHONPATH as in the previous section):
```
cd maskcam
VIDEO_CODEC=avc1 python3 run_yolo.py video_file.mp4
```


### Running on any Ubuntu desktop with GPU and CUDA
1. Edit the file `maskcam/config.yml` and pick a `yolo_variant`, e.g:
```
yolo_variant: yolo_darknet_tiny
```
2. Create a virtualenv with python 3 (tested: 3.7.7)
3. pip install -r requirements.in
4. Run `run_yolo.py` with a custom CUDA installation if needed, e.g:
```
LD_LIBRARY_PATH=/usr/local/cuda-9.0/lib64 python run_yolo.py video_file.mp4
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

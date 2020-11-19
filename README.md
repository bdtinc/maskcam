# MaskCam [BDTi Cube]
Adaptation of the Face Masks Detector to run on Jetson Nano

## Running inference
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

### Running on Jetson Nano
1. Make sure these packages are installed at system level:
```
sudo apt install python3-opencv python3-libnvinfer
```
2. Install the requirements listed on `requirements.in` **excluding** `norfair`.
```
# Before this: remove norfair from requirements.in
pip3 install -r requirements.in
```
3. Clone `norfair` and `filterpy` at the same level that this repo:
```
git clone git@github.com:tryolabs/norfair.git
git clone git@github.com:rlabbe/filterpy.git
```
4. Run `run_yolo.py` adding `norfair` and `filterpy` to the path:
```
cd maskcam
PYTHONPATH=../../norfair:../../filterpy python3 run_yolo.py video_file.mp4
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

# How to convert weights generated using the original darknet implementation to TRT
 1. Clone the pytorch implementation of YOLOv4:
```
git clone git@github.com:Tianxiaomo/pytorch-YOLOv4.git
```
 2. Convert the Darknet model to ONNX using the script in `tool/darknet2onnx.py`, e.g:
```
PYTHONPATH='pytorch-YOLOv4:$PYTHONPATH' python3 pytorch-YOLOv4/tool/darknet2onnx.py yolo/facemask-yolov4-tiny.cfg yolo/facemask-yolov4-tiny_best.weights <optional batch size>
```
 3. Convert the ONNX model to TRT, e.g:
```
/usr/src/tensorrt/bin/trtexec --fp16 --onnx=../yolo/yolov4_1_3_608_608_static.onnx --explicitBatch --saveEngine=tensorrt_fp16.trt
```

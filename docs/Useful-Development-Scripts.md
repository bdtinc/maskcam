# Useful development scripts
These scripts are intended to be used by developers. They require some knowledge on the subject they're used for.

## Running TensorRT engine on images
This script will run the engine on a folder of images, and generate another folder
for the images with the bounding boxes drawn, and the detection score.

To run this script, you need basically the same general instructions that the regular installation, except that you don't need DeepStream and you do need OpenCV instead.

Usage:
```
cd yolo/
python3 run_yolo_images.py path/to/input/folder path/to/output/folder
```

## Debugging MQTT communication
If you want to see the raw messages that the MQTT broker receives,
and be able to send custom messages to the device (at your own risk),
there's a script `maskcam/mqtt_commander.py`, which may be useful for debugging
on your local computer or from the Jetson device itself.

The script connects to the MQTT broker and sniffs all the communication to/from any device to the broker.
```
export MQTT_BROKER_IP=<server ip (local or remote)>
export MQTT_DEVICE_NAME=<device to command>
python3 -m maskcam.mqtt_commander
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

import sys
import os
import time
import argparse
import numpy as np
import cv2
import tensorrt as trt

import pycuda.driver as cuda
import pycuda.autoinit

from norfair.tracker import Detection
from integrations.yolo.utils_pytorch import load_class_names, post_processing


# Simple helper data class that's a little nicer to use than a 2-tuple.
class HostDeviceMem(object):
    def __init__(self, host_mem, device_mem):
        self.host = host_mem
        self.device = device_mem

    def __str__(self):
        return "Host:\n" + str(self.host) + "\nDevice:\n" + str(self.device)

    def __repr__(self):
        return self.__str__()


class DetectorYoloTRT:
    """ Adaptor for the original Yolo implementation (AlexeyAB/darknet) """

    def __init__(self, config):
        self.detection_threshold = config["detection_threshold"]
        self.nms_threshold = config["nms_threshold"]
        self.engine_path = config["engine_file"]
        self.class_names = load_class_names(config["names_file"])

        self.logger = trt.Logger()
        self.runtime = trt.Runtime(self.logger)

        print("Reading engine from file {}".format(self.engine_path))
        with open(self.engine_path, "rb") as f:
            self.engine = self.runtime.deserialize_cuda_engine(f.read())

        self.context = self.engine.create_execution_context()
        self.buffers = self._allocate_buffers(self.engine, 1)

        self.input_h = 608  # Set in yolov4-facemask.cfg
        self.input_w = 608
        self.context.set_binding_shape(0, (1, 3, self.input_h, self.input_w))

    def detect(self, frame, rescale_detections=True):
        orig_height, orig_width = frame.shape[:2]

        # Input
        frame_resized = cv2.resize(
            frame, (self.input_w, self.input_h), interpolation=cv2.INTER_LINEAR
        )
        img_in = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
        img_in = np.transpose(img_in, (2, 0, 1)).astype(np.float32)
        img_in = np.expand_dims(img_in, axis=0)
        img_in /= 255.0
        img_in = np.ascontiguousarray(img_in)

        inputs, outputs, bindings, stream = self.buffers
        inputs[0].host = img_in

        trt_outputs = self._do_inference(
            self.context, bindings=bindings, inputs=inputs, outputs=outputs, stream=stream
        )

        trt_outputs[0] = trt_outputs[0].reshape(1, -1, 1, 4)
        trt_outputs[1] = trt_outputs[1].reshape(1, -1, len(self.class_names))

        # detection threshold + NMS filtering
        detections = post_processing(
            img_in, self.detection_threshold, self.nms_threshold, trt_outputs
        )

        width = orig_width if rescale_detections else self.input_w
        height = orig_height if rescale_detections else self.input_h
        dets = []
        for k, d in enumerate(detections[0]):
            d[0] *= width
            d[1] *= height
            d[2] *= width
            d[3] *= height
            p = d[4]
            label = self.class_names[d[6]]
            dets.append(Detection(np.array((d[0:2], d[2:4])), data={"label": label, "p": p},))
        return dets, frame_resized

    # This function is generalized for multiple inputs/outputs.
    # inputs and outputs are expected to be lists of HostDeviceMem objects.
    def _do_inference(self, context, bindings, inputs, outputs, stream):
        # Transfer input data to the GPU.
        [cuda.memcpy_htod_async(inp.device, inp.host, stream) for inp in inputs]
        # Run inference.
        context.execute_async(bindings=bindings, stream_handle=stream.handle)
        # Transfer predictions back from the GPU.
        [cuda.memcpy_dtoh_async(out.host, out.device, stream) for out in outputs]
        # Synchronize the stream
        stream.synchronize()
        # Return only the host outputs.
        return [out.host for out in outputs]

    # Allocates all buffers required for an engine, i.e. host/device inputs/outputs.
    def _allocate_buffers(self, engine, batch_size):
        inputs = []
        outputs = []
        bindings = []
        stream = cuda.Stream()
        for binding in engine:

            size = trt.volume(engine.get_binding_shape(binding)) * batch_size
            dims = engine.get_binding_shape(binding)

            # in case batch dimension is -1 (dynamic)
            if dims[0] < 0:
                size *= -1

            dtype = trt.nptype(engine.get_binding_dtype(binding))
            # Allocate host and device buffers
            host_mem = cuda.pagelocked_empty(size, dtype)
            device_mem = cuda.mem_alloc(host_mem.nbytes)
            # Append the device buffer to device bindings.
            bindings.append(int(device_mem))
            # Append to the appropriate list.
            if engine.binding_is_input(binding):
                inputs.append(HostDeviceMem(host_mem, device_mem))
            else:
                outputs.append(HostDeviceMem(host_mem, device_mem))
        return inputs, outputs, bindings, stream

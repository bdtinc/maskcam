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

"""
Code based on these implementations:
 - (main) https://github.com/NVIDIA/object-detection-tensorrt-example/blob/master/SSD_Model/utils/inference.py
 - (originally found here) https://github.com/Tianxiaomo/pytorch-YOLOv4/blob/master/demo_trt.py
"""

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
        self.batch_size = config["batch_size"]
        self.input_h = config["input_height"]
        self.input_w = config["input_width"]
        self.detection_threshold = config["detection_threshold"]
        self.nms_threshold = config["nms_threshold"]
        self.engine_path = config["engine_file"]
        self.class_names = load_class_names(config["names_file"])
        if "min_detection_size" in config:
            self.min_size = config["min_detection_size"]
        else:
            self.min_size = 0

        self.logger = trt.Logger()
        self.runtime = trt.Runtime(self.logger)

        print("Reading engine from file {}".format(self.engine_path))
        with open(self.engine_path, "rb") as f:
            self.engine = self.runtime.deserialize_cuda_engine(f.read())

        self.context = self.engine.create_execution_context()
        self.buffers = self._allocate_buffers(self.engine)

        self.context.set_binding_shape(
            0, (self.batch_size, 3, self.input_h, self.input_w)
        )
        self.img_batch = np.zeros((self.batch_size, 3 * self.input_h * self.input_w))

        self.timer_preprocess = 0.0
        self.timer_inference = 0.0
        self.timer_execute = 0.0
        self.timer_postprocess = 0.0
        self.n_frames = 0
        self.n_inferences = 0

    def print_profiler(self):
        print(
            f"Batch size: {self.batch_size}"
            f" | Frames processed: {self.n_frames}"
            f" | # inferences executed: {self.n_inferences}"
        )
        print(
            f"Avg preprocess time/frame:\t{self.timer_preprocess/self.n_frames:.4f}s"
            f"\t| FPS: {self.n_frames / self.timer_preprocess:.1f}"
        )
        print(
            f"Avg inference time/frame:\t{self.timer_inference/self.n_frames:.4f}s"
            f"\t| FPS: {self.n_frames / self.timer_inference:.1f}"
        )
        print(
            f"Avg postprocess time/frame:\t{self.timer_postprocess/self.n_frames:.4f}s"
            f"\t| FPS: {self.n_frames / self.timer_postprocess:.1f}"
        )
        print(
            f"Avg execute time/frame:\t{self.timer_execute/self.n_frames:.4f}s"
            f"\t| FPS: {self.n_frames / self.timer_execute:.1f}"
        )
        print(
            f"Avg execute time/inference:\t{self.timer_execute/self.n_inferences:.4f}s"
        )

    def detect(self, frames, rescale_detections=True):
        inputs, outputs, bindings, stream = self.buffers
        frames_resized = []
        self.n_frames += len(frames)
        tick = time.time()
        for idx, frame in enumerate(frames):
            orig_height, orig_width = frame.shape[:2]

            # Input
            frame_resized = cv2.resize(
                frame, (self.input_w, self.input_h), interpolation=cv2.INTER_LINEAR
            )
            frames_resized.append(frame_resized)
            img_in = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
            img_in = np.transpose(img_in, (2, 0, 1)).astype(np.float32)
            # img_in = np.expand_dims(img_in, axis=0)
            img_in /= 255.0
            # img_in = np.ascontiguousarray(img_in)
            self.img_batch[idx] = img_in.ravel()
        np.copyto(inputs[0].host, self.img_batch.ravel())
        self.timer_preprocess += time.time() - tick
        tick = time.time()

        trt_outputs = self._do_inference(
            self.context,
            bindings=bindings,
            inputs=inputs,
            outputs=outputs,
            stream=stream,
        )
        self.timer_inference += time.time() - tick

        trt_outputs[0] = trt_outputs[0].reshape(self.batch_size, -1, 1, 4)
        trt_outputs[1] = trt_outputs[1].reshape(
            self.batch_size, -1, len(self.class_names)
        )

        # detection threshold + NMS filtering
        tick = time.time()
        detections = post_processing(
            img_in, self.detection_threshold, self.nms_threshold, trt_outputs
        )
        self.timer_postprocess += time.time() - tick
        dets_batches = []

        for batch_idx in range(len(detections)):
            width = orig_width if rescale_detections else self.input_w
            height = orig_height if rescale_detections else self.input_h
            dets = []
            for k, d in enumerate(detections[batch_idx]):
                d[0] *= width
                d[1] *= height
                d[2] *= width
                d[3] *= height
                if self.min_size:
                    detection_width = d[2] - d[0]
                    detection_height = d[3] - d[1]
                    if min(detection_height, detection_width) < self.min_size:
                        break
                p = d[4]
                label = self.class_names[d[6]]
                dets.append(
                    Detection(
                        np.array((d[0:2], d[2:4])),
                        data={"label": label, "p": p},
                    )
                )
            dets_batches.append(dets)
        return dets_batches, frames_resized

    # This function is generalized for multiple inputs/outputs.
    # inputs and outputs are expected to be lists of HostDeviceMem objects.
    def _do_inference(self, context, bindings, inputs, outputs, stream):
        self.n_inferences += 1
        tick = time.time()
        # Transfer input data to the GPU.
        [cuda.memcpy_htod_async(inp.device, inp.host, stream) for inp in inputs]
        # Run inference.
        context.execute_async_v2(bindings=bindings, stream_handle=stream.handle)
        # Transfer predictions back from the GPU.
        [cuda.memcpy_dtoh_async(out.host, out.device, stream) for out in outputs]
        # Synchronize the stream
        stream.synchronize()
        # In this case, we measure the memcpy + execute ops together (small difference)
        self.timer_execute += time.time() - tick
        # Return only the host outputs.
        return [out.host for out in outputs]

    def _do_inference_sync(self, context, bindings, inputs, outputs, stream):
        self.n_inferences += 1
        # Transfer input data to the GPU.
        [cuda.memcpy_htod(inp.device, inp.host) for inp in inputs]
        # Run inference.
        tick = time.time()
        context.execute_v2(bindings=bindings)
        self.timer_execute += time.time() - tick
        # Transfer predictions back from the GPU.
        [cuda.memcpy_dtoh(out.host, out.device) for out in outputs]
        # Return only the host outputs.
        return [out.host for out in outputs]

    # Allocates all buffers required for an engine, i.e. host/device inputs/outputs.
    def _allocate_buffers(self, engine):
        inputs = []
        outputs = []
        bindings = []
        stream = cuda.Stream()
        for binding in engine:

            # engine.max_batch_size is 1 for static batch
            size = (
                trt.volume(engine.get_binding_shape(binding))
                * self.engine.max_batch_size
            )
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

    # Allocates all buffers required for an engine, i.e. host/device inputs/outputs.
    def _allocate_buffers(self, engine):
        inputs = []
        outputs = []
        bindings = []
        stream = cuda.Stream()
        for binding in engine:

            # engine.max_batch_size is 1 for static batch
            size = (
                trt.volume(engine.get_binding_shape(binding))
                * self.engine.max_batch_size
            )
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

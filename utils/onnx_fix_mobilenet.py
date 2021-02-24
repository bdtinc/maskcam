import sys
import onnx_graphsurgeon as gs
import onnx
import numpy as np

"""
This code is intended to change the uint8 input type (not supported by TensorRT)
The input ONNX file can be produced by converting with:
https://github.com/onnx/tensorflow-onnx

After conversion, the output ONNX should be able to be converted as:
/usr/src/tensorrt/bin/trtexec --fp16 --onnx=input_file.onnx --explicitBatch --saveEngine=output_file.trt
But that step still fails due to NonMaxSuppression plugin not found (operation not supported by TensorRT)
"""

input_onnx = sys.argv[1]
output_onnx = sys.argv[2]
graph = gs.import_onnx(onnx.load(input_onnx))
for inp in graph.inputs:
    inp.dtype = np.float32

onnx.save(gs.export_onnx(graph), output_onnx)

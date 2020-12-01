import sys
import tensorflow as tf
from tensorflow.python.compiler.tensorrt import trt_convert as trt

input_saved_model_dir = sys.argv[1]
output_saved_model_dir = sys.argv[2]

"""
This code is based on:
 - https://docs.nvidia.com/deeplearning/frameworks/tf-trt-user-guide/index.html#worflow-with-savedmodel
 - https://sayak.dev/tf.keras/tensorrt/tensorflow/2020/07/01/accelerated-inference-trt.html

Currently fails after a while (jetson, tensorflow==2.3.1) with:

2020-11-27 16:32:23.116411: W tensorflow/core/framework/op_kernel.cc:1767] OP_REQUIRES failed at trt_engine_resource_ops.cc:196 : Not found: Container TF-TRT does not exist. (Could not find resource: TF-TRT/TRTEngineOp_0_0)
"""

conversion_params = trt.DEFAULT_TRT_CONVERSION_PARAMS
# conversion_params = conversion_params._replace(max_workspace_size_bytes=(1 << 32))
conversion_params = conversion_params._replace(precision_mode="FP16")
conversion_params = conversion_params._replace(maximum_cached_engines=100)

converter = trt.TrtGraphConverterV2(
    input_saved_model_dir=input_saved_model_dir, conversion_params=conversion_params
)
converter.convert()

converter.save(output_saved_model_dir)


# saved_model_loaded = tf.saved_model.load(
#     output_saved_model_dir, tags=[tag_constants.SERVING])
# graph_func = saved_model_loaded.signatures[
#     signature_constants.DEFAULT_SERVING_SIGNATURE_DEF_KEY]
# frozen_func = convert_to_constants.convert_variables_to_constants_v2(
#     graph_func)
# output = frozen_func(input_data)[0].numpy()

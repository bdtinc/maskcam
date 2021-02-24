import tensorflow as tf
from tensorflow.python.compiler.tensorrt import trt_convert
import tensorflow.contrib.tensorrt as trt


"""
Code based on:
 - https://docs.nvidia.com/deeplearning/frameworks/tf-trt-user-guide/index.html#using-savedmodel
 - https://github.com/NVIDIA-AI-IOT/tf_trt_models/blob/master/examples/detection/detection.ipynb
"""

# converter = trt_convert.TrtGraphConverter(
#     input_saved_model_dir=input_saved_model_dir,
#     precision_mode=”FP16”,
#     maximum_cached_engines=100)
# converter.convert()
# converter.save(output_saved_model_dir)

# with tf.Session() as sess:
#     # First load the SavedModel into the session
#     tf.saved_model.loader.load(
#         sess, [tf.saved_model.tag_constants.SERVING],
#        output_saved_model_dir)
#     output = sess.run([output_tensor], feed_dict={input_tensor: input_data})

input_name = ["image_tensor"]
output_names = [
    "detection_boxes",
    "detection_classes",
    "detection_scores",
    "num_detections",
]

tf_config.gpu_options.allow_growth = True
tf_sess = tf.Session(config=tf_config)
tf.import_graph_def(trt_graph, name="")

tf_input = tf_sess.graph.get_tensor_by_name(input_names[0] + ":0")
tf_scores = tf_sess.graph.get_tensor_by_name("detection_scores:0")
tf_boxes = tf_sess.graph.get_tensor_by_name("detection_boxes:0")
tf_classes = tf_sess.graph.get_tensor_by_name("detection_classes:0")
tf_num_detections = tf_sess.graph.get_tensor_by_name("num_detections:0")

trt_graph = trt.create_inference_graph(
    input_graph_def=frozen_graph,
    outputs=output_names,
    max_batch_size=1,
    max_workspace_size_bytes=1 << 25,
    precision_mode="FP16",
    minimum_segment_size=50,
)

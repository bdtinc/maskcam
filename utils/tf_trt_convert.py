# %%
import sys
import os
import time
import urllib
import matplotlib
import numpy as np
import tensorflow as tf
import tensorflow.contrib.tensorrt as trt

matplotlib.use("Agg")

from PIL import Image

# Install this from: https://github.com/NVIDIA-AI-IOT/tf_trt_models
# Tested on Nano with python 3.6.9 and TF-1.15.4
from tf_trt_models.detection import download_detection_model, build_detection_graph

import matplotlib.pyplot as plt
import matplotlib.patches as patches

# %%
# inference_graph_path = "../inference_graph_1024x608"
# inference_graph_path = "../inference_graph_300x300"
inference_graph_path = "../inference_graph_400x708"
config_path = f"{inference_graph_path}/pipeline.config"
checkpoint_path = f"{inference_graph_path}/model.ckpt"
batch_size = 4
score_threshold = 0.5  # TODO: Try this, with 0.5 in 300x300 and check results w/slack

frozen_graph, input_names, output_names = build_detection_graph(
    config=config_path,
    checkpoint=checkpoint_path,
    batch_size=batch_size,
    score_threshold=score_threshold,
)
# %%

trt_graph = trt.create_inference_graph(
    input_graph_def=frozen_graph,
    outputs=output_names,
    max_batch_size=batch_size,
    max_workspace_size_bytes=1 << 25,
    precision_mode="FP16",
    minimum_segment_size=50,
)

# %%
converted_trt_graph_file = f"converted_trt_708_400_bs{batch_size}.pb"
# %%
with open(converted_trt_graph_file, "wb") as f:
    f.write(trt_graph.SerializeToString())

# %%
trt_graph = tf.GraphDef()
with open(converted_trt_graph_file, "rb") as f:
    trt_graph.ParseFromString(f.read())
# %%
input_names = ["image_tensor"]
output_names = [
    "detection_boxes",
    "detection_classes",
    "detection_scores",
    "num_detections",
]


# %%
tf_config = tf.ConfigProto()
tf_config.gpu_options.allow_growth = True

tf_sess = tf.Session(config=tf_config)

tf.import_graph_def(trt_graph, name="")

tf_input = tf_sess.graph.get_tensor_by_name(input_names[0] + ":0")
tf_scores = tf_sess.graph.get_tensor_by_name("detection_scores:0")
tf_boxes = tf_sess.graph.get_tensor_by_name("detection_boxes:0")
tf_classes = tf_sess.graph.get_tensor_by_name("detection_classes:0")
tf_num_detections = tf_sess.graph.get_tensor_by_name("num_detections:0")

# %%
paths = ["../yolo/data/obj_train_data/images/hdstock_2_90.jpg"]
paths += ["../yolo/data/obj_train_data/images/1_30s_0.jpg"]
image = Image.open(paths[0])

plt.imshow(image)

# image_resized = np.array(image.resize((1024, 608)))
# image_resized = np.array(image.resize((300, 300)))
image_resized = np.array(image.resize((708, 400)))
image = np.array(image)

# %%
scores, boxes, classes, num_detections = tf_sess.run(
    [tf_scores, tf_boxes, tf_classes, tf_num_detections],
    feed_dict={tf_input: np.stack([image_resized] * batch_size)},
)

boxes = boxes[0]  # index by 0 to remove batch dimension
scores = scores[0]
classes = classes[0]
num_detections = num_detections[0]

# %%
fig = plt.figure()
ax = fig.add_subplot(1, 1, 1)

ax.imshow(image)

# plot boxes exceeding score threshold
for i in range(int(num_detections)):
    # scale box to image coordinates
    box = boxes[i] * np.array(
        [image.shape[0], image.shape[1], image.shape[0], image.shape[1]]
    )

    # display rectangle
    patch = patches.Rectangle(
        (box[1], box[0]), box[3] - box[1], box[2] - box[0], color="g", alpha=0.3
    )
    ax.add_patch(patch)

    # display class index and score
    plt.text(
        x=box[1] + 10,
        y=box[2] - 10,
        s="%d (%0.2f) " % (classes[i], scores[i]),
        color="w",
    )
plt.savefig("detections.png")

# %%
num_samples = 50

input_batch = np.stack([image_resized] * batch_size)
t0 = time.time()
for i in range(num_samples):
    scores, boxes, classes, num_detections = tf_sess.run(
        [tf_scores, tf_boxes, tf_classes, tf_num_detections],
        feed_dict={tf_input: input_batch},
    )
t1 = time.time()
print("Average runtime: %f seconds" % (float(t1 - t0) / num_samples))

# %%
tf_sess.close()

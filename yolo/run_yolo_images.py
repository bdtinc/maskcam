################################################################################
# Copyright (c) 2020-2021, Berkeley Design Technology, Inc. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
################################################################################

# %%
import os
import cv2
import sys
import yaml
import time
import glob

from integrations.yolo.yolo_adaptor import YoloAdaptor

# Requires python tensorrt, usually compiled for python 3.6 at system level
from integrations.yolo.detector_trt import DetectorYoloTRT

# %%
images_folder = sys.argv[1]
output_folder = sys.argv[2]

print(f"Scanning input directory: {images_folder}")
images = []
for filetype in ["png", "jpg", "jpeg"]:  # No uppercase for now
    images += glob.glob(f"{images_folder}/*.{filetype}")
print(f"Found {len(images)} images")

if input(f"Confirm output to [{output_folder}] [y/n]").strip() != "y":
    print("Not confirmed. Exiting")
    exit(0)

os.system(f"mkdir -p {output_folder}")

# %%
with open("config_images.yml", "r") as stream:
    # Not using Loader=yaml.FullLoader since it doesn't work on jetson PyYAML version
    config = yaml.load(stream)

yolo_config = {**config["yolo_trt_tiny"], **config["yolo_generic"]}

detector = DetectorYoloTRT(yolo_config)

# Converter functions from Yolo -> Tracker + FaceMaskDetector
pose_adaptor = YoloAdaptor(config["yolo_generic"])

detector_output = config["debug"]["output_detector_resolution"]

for k, image_filename in enumerate(images):

    frame = cv2.imread(image_filename)
    if (
        detector_output
    ):  # Only for debugging purposes: use resized frame in video output
        detections, frames_resized = detector.detect([frame], rescale_detections=False)
        frame = frames_resized[0]
    else:
        detections, _ = detector.detect([frame], rescale_detections=True)
    detections = detections[0]  # Remove batch dimension

    # Drawing functions
    if config["debug"]["draw_detections"]:  # Raw yolo detections
        pose_adaptor.draw_raw_detections(frame, detections)

    im_basename = image_filename.split("/")[-1]
    image_outfile = f"{output_folder}/{im_basename}"
    cv2.imwrite(image_outfile, frame)
    print(f"Writing [{k}/{len(images)}]: {image_outfile}")

if config["debug"]["profiler"]:
    detector.print_profiler()

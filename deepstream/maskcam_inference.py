#!/usr/bin/env python3

################################################################################
# Copyright (c) 2020, NVIDIA CORPORATION. All rights reserved.
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

import os
import gi
import pyds
import sys
import json
import ipdb
import time
import signal
import platform
import threading
import configparser
import numpy as np
import multiprocessing as mp
from rich import print
from rich.console import Console
from datetime import datetime, timezone
from paho.mqtt import client as paho_mqtt_client


gi.require_version("Gst", "1.0")
gi.require_version("GstRtspServer", "1.0")
from gi.repository import GLib, Gst, GstRtspServer

sys.path.append("../../norfair")
sys.path.append("../../filterpy")
from norfair.tracker import Tracker, Detection
from common import CODEC_MP4, CODEC_H264, CODEC_H265, USBCAM_PROTOCOL, RASPICAM_PROTOCOL, CONFIG_FILE


# YOLO labels. See obj.names file
PGIE_CLASS_ID_MASK = 0
PGIE_CLASS_ID_NO_MASK = 1
PGIE_CLASS_ID_NOT_VISIBLE = 2
PGIE_CLASS_ID_MISPLACED = 3

# MQTT topics
TOPIC_HELLO = "hello"
TOPIC_STATS = "receive-from-jetson"
TOPIC_ALERTS = "alerts"

# Must come defined as environment var or MQTT gets disabled
MQTT_BROKER_IP = os.environ.get("MQTT_BROKER_IP", None)
MQTT_DEVICE_NAME = os.environ.get("MQTT_DEVICE_NAME", None)
MQTT_DEVICE_DESCRIPTION = "MaskCam @ Jetson Nano"

FRAMES_LOG_INTERVAL = 50

# Global vars
frame_number = 0
start_time = None
end_time = None
total_frames = 0
mqtt_client = None
console = Console()
e_interrupt = None


class FaceMask:
    def __init__(self, th_detection, th_vote, min_face_size):
        self.people_votes = {}
        self.current_people = set()
        self.th_detection = th_detection
        self.th_vote = th_vote
        self.min_face_size = min_face_size
        self.disable_detection_validation = False
        self.min_votes = 5
        self.max_votes = 50
        self.color_mask = (0.0, 1.0, 0.0)  # green
        self.color_no_mask = (1.0, 0.0, 0.0)  # red
        self.color_unknown = (1.0, 1.0, 0.0)  # yellow
        self.draw_raw_detections = True
        self.draw_tracked_people = True
        self.tracker_enabled = False
        self.stats_lock = threading.Lock()

    def validate_detection(self, box_points, score, label):
        if self.disable_detection_validation:
            return True
        box_width = box_points[1][0] - box_points[0][0]
        box_height = box_points[1][1] - box_points[0][1]
        return (
            min(box_width, box_height) >= self.min_face_size
            and score >= self.th_detection
        )

    def add_detection(self, person_id, label, score):
        # This function is called from streaming thread
        with self.stats_lock:
            self.current_people.add(person_id)
            if person_id not in self.people_votes:
                self.people_votes[person_id] = 0
            if score > self.th_vote:
                if label == "mask":
                    self.people_votes[person_id] += 1
                elif label == "no_mask" or "misplaced":
                    self.people_votes[person_id] -= 1
                # max_votes limit
                self.people_votes[person_id] = np.clip(
                    self.people_votes[person_id], -self.max_votes, self.max_votes
                )

    def get_person_label(self, person_id):
        person_votes = self.people_votes[person_id]
        if abs(person_votes) >= self.min_votes:
            color = self.color_mask if person_votes > 0 else self.color_no_mask
            label = "mask" if person_votes > 0 else "no mask"
        else:
            color = self.color_unknown
            label = "not visible"
        return f"{person_id}|{label}({abs(person_votes)})", color

    def get_instant_statistics(self, refresh=True):
        """
        Get statistics only including people that appeared on camera since last refresh
        """
        instant_stats = self.get_statistics(filter_ids=self.current_people)
        if refresh:
            with self.stats_lock:
                self.current_people = set()
        return instant_stats

    def get_statistics(self, filter_ids=None):
        with self.stats_lock:
            if filter_ids is not None:
                filtered_people = {
                    id: votes
                    for id, votes in self.people_votes.items()
                    if id in filter_ids
                }
            else:
                filtered_people = self.people_votes
            total_people = len(filtered_people)
            total_classified = 0
            total_mask = 0
            for person_id in filtered_people:
                person_votes = filtered_people[person_id]
                if abs(person_votes) >= self.min_votes:
                    total_classified += 1
                    if person_votes > 0:
                        total_mask += 1
        return total_people, total_classified, total_mask


def keypoints_distance(detected_pose, tracked_pose):
    detected_points = detected_pose.points
    estimated_pose = tracked_pose.estimate
    min_box_size = min(
        max(
            detected_points[1][0] - detected_points[0][0],  # x2 - x1
            detected_points[1][1] - detected_points[0][1],  # y2 - y1
            1,
        ),
        max(
            estimated_pose[1][0] - estimated_pose[0][0],  # x2 - x1
            estimated_pose[1][1] - estimated_pose[0][1],  # y2 - y1
            1,
        ),
    )
    mean_distance_normalized = (
        np.mean(np.linalg.norm(detected_points - estimated_pose, axis=1)) / min_box_size
    )
    return mean_distance_normalized


face_mask = FaceMask(0.1, 0.4, 0)

# In Norfair we trust
tracker = Tracker(
    distance_function=keypoints_distance,
    detection_threshold=face_mask.th_detection,
    distance_threshold=1,
    point_transience=8,
    hit_inertia_min=25,
    hit_inertia_max=60,
)


def connect_mqtt_broker(
    client_id: str, broker_ip: str, broker_port: int
) -> paho_mqtt_client:
    def on_connect(client, userdata, flags, code):
        if code == 0:
            print("Connected to MQTT Broker")
            say_hello()
        else:
            print(f"Failed to connect, return code {code}\n")

    client = paho_mqtt_client.Client(client_id)
    client.on_connect = on_connect
    client.connect(broker_ip, broker_port)
    return client


def send_mqtt_msg(topic, message):
    # TODO: Handle queuing if mqtt_client not connected
    result = mqtt_client.publish(topic, json.dumps(message))
    if result[0] == 0:
        console.log(f"MQTT message [green]SENT [bold][topic: {topic}][/bold][/green]")
    else:
        console.log(f"MQTT message [red]FAILED [bold][topic: {topic}][/bold][/red]")
    print(message)


def say_hello():
    send_mqtt_msg(
        TOPIC_HELLO, {"id": MQTT_DEVICE_NAME, "description": MQTT_DEVICE_DESCRIPTION}
    )


def cb_send_statistics(cb_args):
    mqtt_send_period = cb_args
    # Test topic
    topic = TOPIC_STATS  # TODO: implement TOPIC_ALERTS
    people_total, people_classified, people_mask = face_mask.get_instant_statistics(
        refresh=True
    )
    people_no_mask = people_classified - people_mask
    message = {
        "device_id": MQTT_DEVICE_NAME,
        "people_total": people_total,
        "people_with_mask": people_mask,
        "people_without_mask": people_no_mask,
        "timestamp": datetime.timestamp(datetime.now(timezone.utc)),
    }
    send_mqtt_msg(topic, message)

    # Next report timeout
    GLib.timeout_add_seconds(mqtt_send_period, cb_send_statistics, cb_args)


def sigint_handler(sig, frame):
    # This function is not used if e_external_interrupt is provided
    print("\n[red]Ctrl+C pressed. Interrupting...[/red]")
    e_interrupt.set()


def is_aarch64():
    return platform.uname()[4] == "aarch64"


def draw_detection(display_meta, n_draw, box_points, detection_label, color):
    # print(f"Drawing {n_draw} | {detection_label}")
    # print(box_points)
    rect = display_meta.rect_params[n_draw]

    ((x1, y1), (x2, y2)) = box_points
    rect.left = x1
    rect.top = y1
    rect.width = x2 - x1
    rect.height = y2 - y1
    # print(f"{x1} {y1}, {x2} {y2}")
    # Bug: bg color is always green
    # rect.has_bg_color = True
    # rect.bg_color.set(0.5, 0.5, 0.5, 0.6)  # RGBA
    rect.border_color.set(*color, 1.0)
    rect.border_width = 2
    label = display_meta.text_params[n_draw]
    label.x_offset = x1
    label.y_offset = y2
    label.font_params.font_name = "Verdana"
    label.font_params.font_size = 9
    label.font_params.font_color.set(0, 0, 0, 1.0)  # Black
    # label.display_text = f"{person.id} | {detection_p:.2f}"
    label.display_text = detection_label
    label.set_bg_clr = True
    label.text_bg_clr.set(*color, 0.5)

    display_meta.num_rects = n_draw + 1
    display_meta.num_labels = n_draw + 1


def osd_sink_pad_buffer_probe(pad, info, u_data):
    global frame_number
    global start_time
    global total_frames  # Redundant w/ frame_number
    # print(".", end="", flush=True)
    # Intiallizing object counter with 0.
    obj_counter = {
        PGIE_CLASS_ID_MASK: 0,
        PGIE_CLASS_ID_NO_MASK: 0,
        PGIE_CLASS_ID_NOT_VISIBLE: 0,
        PGIE_CLASS_ID_MISPLACED: 0,
    }

    gst_buffer = info.get_buffer()
    if not gst_buffer:
        console.log("Unable to get GstBuffer ")
        return

    # Retrieve batch metadata from the gst_buffer
    # Note that pyds.gst_buffer_get_nvds_batch_meta() expects the
    # C address of gst_buffer as input, which is obtained with hash(gst_buffer)
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    if not total_frames % FRAMES_LOG_INTERVAL:
        console.log(f"Processed {total_frames} frames...")

    l_frame = batch_meta.frame_meta_list
    while l_frame is not None:
        total_frames += 1
        try:
            # Note that l_frame.data needs a cast to pyds.NvDsFrameMeta
            # The casting is done by pyds.glist_get_nvds_frame_meta()
            # The casting also keeps ownership of the underlying memory
            # in the C code, so the Python garbage collector will leave
            # it alone.
            # frame_meta = pyds.glist_get_nvds_frame_meta(l_frame.data)
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
        except StopIteration:
            break

        frame_number = frame_meta.frame_num
        # num_detections = frame_meta.num_obj_meta
        l_obj = frame_meta.obj_meta_list
        detections = []
        obj_meta_list = []
        while l_obj is not None:
            try:
                # Casting l_obj.data to pyds.NvDsObjectMeta
                # obj_meta=pyds.glist_get_nvds_object_meta(l_obj.data)
                obj_meta = pyds.NvDsObjectMeta.cast(l_obj.data)
            except StopIteration:
                break
            obj_meta_list.append(obj_meta)
            obj_counter[obj_meta.class_id] += 1
            obj_meta.rect_params.border_color.set(0.0, 0.0, 1.0, 0.0)
            box = obj_meta.rect_params
            # print(f"{obj_meta.obj_label} | {obj_meta.confidence}")

            box_points = (
                (box.left, box.top),
                (box.left + box.width, box.top + box.height),
            )
            box_p = obj_meta.confidence
            box_label = obj_meta.obj_label
            if face_mask.validate_detection(box_points, box_p, box_label):
                det_data = {"label": box_label, "p": box_p}
                detections.append(
                    Detection(
                        np.array(box_points),
                        data=det_data,
                    )
                )
                # print(f"Added detection: {det_data}")
            try:
                l_obj = l_obj.next
            except StopIteration:
                break

        # Remove all object meta to avoid drawing. Do this outside while since we're modifying list
        for obj_meta in obj_meta_list:
            # Remove this to avoid drawing label texts
            pyds.nvds_remove_obj_meta_from_frame(frame_meta, obj_meta)
        obj_meta_list = None

        # Each meta object carries max 16 rects/labels/etc.
        max_drawings_per_meta = 16  # This is hardcoded, not documented

        if face_mask.tracker_enabled:
            # Track, count and draw tracked people
            tracked_people = tracker.update(detections)
            # Filter out people with no live points (don't draw)
            drawn_people = [
                person for person in tracked_people if person.live_points.any()
            ]

            if face_mask.draw_tracked_people:
                for n_person, person in enumerate(drawn_people):
                    points = person.estimate
                    box_points = points.clip(0).astype(int)

                    # Update mask votes
                    face_mask.add_detection(
                        person.id,
                        person.last_detection.data["label"],
                        person.last_detection.data["p"],
                    )
                    label, color = face_mask.get_person_label(person.id)

                    # Index of this person's drawing in the current meta
                    n_draw = n_person % max_drawings_per_meta

                    if n_draw == 0:  # Initialize meta
                        # Acquiring a display meta object. The memory ownership remains in
                        # the C code so downstream plugins can still access it. Otherwise
                        # the garbage collector will claim it when this probe function exits.
                        display_meta = pyds.nvds_acquire_display_meta_from_pool(
                            batch_meta
                        )
                        pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)

                    draw_detection(display_meta, n_draw, box_points, label, color)

        # Raw detections
        if face_mask.draw_raw_detections:
            for n_detection, detection in enumerate(detections):
                points = detection.points
                box_points = points.clip(0).astype(int)
                label = detection.data["label"]
                if label == "mask":
                    color = face_mask.color_mask
                elif label == "no_mask" or label == "misplaced":
                    color = face_mask.color_no_mask
                else:
                    color = face_mask.color_unknown
                label = f"{label} | {detection.data['p']:.2f}"
                n_draw = n_detection % max_drawings_per_meta

                if n_draw == 0:  # Initialize meta
                    # Acquiring a display meta object. The memory ownership remains in
                    # the C code so downstream plugins can still access it. Otherwise
                    # the garbage collector will claim it when this probe function exits.
                    display_meta = pyds.nvds_acquire_display_meta_from_pool(batch_meta)
                    pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)
                draw_detection(display_meta, n_draw, box_points, label, color)

            # Using pyds.get_string() to get display_text as string
            # print(pyds.get_string(py_nvosd_text_params.display_text))
            # print(".", end="", flush=True)
        # print("")

        try:
            l_frame = l_frame.next
        except StopIteration:
            break
    # Start timer at the end of first frame processing
    if start_time is None:
        start_time = time.time()
    return Gst.PadProbeReturn.OK


def cb_newpad(decodebin, decoder_src_pad, data):
    print("In cb_newpad\n")
    caps = decoder_src_pad.get_current_caps()
    gststruct = caps.get_structure(0)
    gstname = gststruct.get_name()
    source_bin = data
    features = caps.get_features(0)

    # Need to check if the pad created by the decodebin is for video and not
    # audio.
    print("gstname=", gstname)
    if gstname.find("video") != -1:
        # Link the decodebin pad only if decodebin has picked nvidia
        # decoder plugin nvdec_*. We do this by checking if the pad caps contain
        # NVMM memory features.
        print("features=", features)
        if features.contains("memory:NVMM"):
            # Get the source bin ghost pad
            bin_ghost_pad = source_bin.get_static_pad("src")
            if not bin_ghost_pad.set_target(decoder_src_pad):
                sys.stderr.write(
                    "Failed to link decoder src pad to source bin ghost pad\n"
                )
        else:
            sys.stderr.write(" Error: Decodebin did not pick nvidia decoder plugin.\n")


def decodebin_child_added(child_proxy, Object, name, user_data):
    print(f"Decodebin child added: {name}")
    if name.find("decodebin") != -1:
        Object.connect("child-added", decodebin_child_added, user_data)
    if is_aarch64() and name.find("nvv4l2decoder") != -1:
        Object.set_property("bufapi-version", True)


def create_source_bin(index, uri):
    print("Creating source bin")

    # Create a source GstBin to abstract this bin's content from the rest of the
    # pipeline
    bin_name = "source-bin-%02d" % index
    print(bin_name)
    nbin = Gst.Bin.new(bin_name)
    if not nbin:
        sys.stderr.write(" Unable to create source bin \n")

    # Source element for reading from the uri.
    # We will use decodebin and let it figure out the container format of the
    # stream and the codec and plug the appropriate demux and decode plugins.
    uri_decode_bin = Gst.ElementFactory.make("uridecodebin", "uri-decode-bin")
    if not uri_decode_bin:
        sys.stderr.write(" Unable to create uri decode bin \n")
    # We set the input uri to the source element
    uri_decode_bin.set_property("uri", uri)
    # Connect to the "pad-added" signal of the decodebin which generates a
    # callback once a new pad for raw data has beed created by the decodebin
    uri_decode_bin.connect("pad-added", cb_newpad, nbin)
    uri_decode_bin.connect("child-added", decodebin_child_added, nbin)

    # We need to create a ghost pad for the source bin which will act as a proxy
    # for the video decoder src pad. The ghost pad will not have a target right
    # now. Once the decode bin creates the video decoder and generates the
    # cb_newpad callback, we will set the ghost pad target to the video decoder
    # src pad.
    Gst.Bin.add(nbin, uri_decode_bin)
    bin_pad = nbin.add_pad(Gst.GhostPad.new_no_target("src", Gst.PadDirection.SRC))
    if not bin_pad:
        sys.stderr.write(" Failed to add ghost pad in source bin \n")
        return None
    return nbin


def make_elm_or_print_err(factoryname, name, printedname):
    """Creates an element with Gst Element Factory make.
    Return the element  if successfully created, otherwise print
    to stderr and return None.
    """
    print("Creating", printedname)
    elm = Gst.ElementFactory.make(factoryname, name)
    if not elm:
        sys.stderr.write("Unable to create " + printedname + " \n")
        show_troubleshooting()
    return elm


def show_troubleshooting():
    # On Jetson, there is a problem with the encoder failing to initialize
    # due to limitation on TLS usage. To work around this, preload libgomp.
    # Add a reminder here in case the user forgets.
    print(
        """
    [yellow]TROUBLESHOOTING HELP[/yellow]

    [yellow]If the error is like: v4l-camera-source / reason not-negotiated[/yellow]
    [green]Solution:[/green] configure camera capabilities
    Run the script under utils/gst_capabilities.sh and find a line with type
    video/x-raw, and a framerate below 14, e.g: 10/1 or 5/1.
    Then edit config_maskcam.txt and change the line:
    camera-framerate=10/1

    [yellow]If the error is like:
    /usr/lib/aarch64-linux-gnu/libgomp.so.1: cannot allocate memory in static TLS block[/yellow]
    [green]Solution:[/green] preload the offending library
    export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1

    [yellow]END HELP[/yellow]
    """
    )


def main(
    config: dict,
    input_filename: str,
    output_filename: str = None,
    e_external_interrupt: mp.Event = None,
):
    global frame_number
    global total_frames
    global start_time
    global end_time
    global e_interrupt
    global mqtt_client

    udp_port = int(config["maskcam"]["udp-port"])
    codec = config["maskcam"]["codec"]
    mqtt_broker_port = int(config["maskcam"]["mqtt-broker-port"])
    mqtt_send_period = int(config["maskcam"]["mqtt-send-period"])
    inference_interval = int(config["property"]["interval"])

    camera_framerate = config["maskcam"]["camera-framerate"]  # e.g: 10/1, 15/1

    # Input camera configuration
    # Use ./gst_capabilities.sh to get the list of available capabilities from /dev/video0
    camera_capabilities = f"video/x-raw, framerate={camera_framerate}"

    # Original: 1920x1080, bdti_resized: 1024x576, yolo-input: 1024x608
    output_width = 1024
    output_height = 576
    output_bitrate = 6000000  # Nice for h264@1024x576: 4000000

    if MQTT_BROKER_IP is None or MQTT_DEVICE_NAME is None:
        print(
            "\nMQTT is DISABLED since MQTT_BROKER_IP or MQTT_DEVICE_NAME env vars are not defined\n"
        )
    else:
        print(f"\nConnecting to MQTT server IP: {MQTT_BROKER_IP}")
        print(f"Device name: {MQTT_DEVICE_NAME}\n\n")
        mqtt_client = connect_mqtt_broker(
            client_id=MQTT_DEVICE_NAME,
            broker_ip=MQTT_BROKER_IP,
            broker_port=mqtt_broker_port,
        )
        mqtt_client.loop_start()

    # Standard GStreamer initialization
    # GObject.threads_init()  # Doesn't seem necessary (see https://pygobject.readthedocs.io/en/latest/guide/threading.html)
    Gst.init(None)

    # Create gstreamer elements
    # Create Pipeline element that will form a connection of other elements
    print("Creating Pipeline \n ")
    pipeline = Gst.Pipeline()

    if not pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")

    # Two types of camera supported: USB or Raspi
    usbcam_input = USBCAM_PROTOCOL in input_filename
    raspicam_input = RASPICAM_PROTOCOL in input_filename
    camera_input = usbcam_input or raspicam_input
    if camera_input:
        if usbcam_input:
            input_device = input_filename[len(USBCAM_PROTOCOL) :]
            source = make_elm_or_print_err("v4l2src", "v4l2-camera-source", "Camera input")
            source.set_property("device", input_device)
        elif raspicam_input:
            input_device = int(input_filename[len(RASPICAM_PROTOCOL) :])
            source = make_elm_or_print_err("nvarguscamerasrc", "nv-argus-camera-source", "RaspiCam input")
            source.set_property("sensor-id", input_device)

        # Misterious converting sequence from deepstream_test_1_usb.py
        caps_camera = make_elm_or_print_err(
            "capsfilter", "camera_src_caps", "Camera caps filter"
        )
        caps_camera.set_property(
            "caps",
            Gst.Caps.from_string(camera_capabilities),
        )
        vidconvsrc = make_elm_or_print_err(
            "videoconvert", "convertor_src1", "Convertor src 1"
        )
        nvvidconvsrc = make_elm_or_print_err(
            "nvvideoconvert", "convertor_src2", "Convertor src 2"
        )
        caps_vidconvsrc = make_elm_or_print_err(
            "capsfilter", "nvmm_caps", "NVMM caps for input stream"
        )
        caps_vidconvsrc.set_property(
            "caps", Gst.Caps.from_string("video/x-raw(memory:NVMM)")
        )
    else:
        source_bin = create_source_bin(0, input_filename)

    # Create nvstreammux instance to form batches from one or more sources.
    streammux = make_elm_or_print_err("nvstreammux", "Stream-muxer", "NvStreamMux")
    streammux.set_property("width", output_width)
    streammux.set_property("height", output_height)
    streammux.set_property(
        "enable-padding", True
    )  # Keeps aspect ratio, but adds black margin
    streammux.set_property("batch-size", 1)
    streammux.set_property("batched-push-timeout", 4000000)

    # Adding this element after muxer will cause detections to get delayed
    # videorate = make_elm_or_print_err("videorate", "Vide-rate", "Video Rate")

    # Inference element: object detection using TRT engine
    pgie = make_elm_or_print_err("nvinfer", "primary-inference", "pgie")
    pgie.set_property("config-file-path", CONFIG_FILE)

    # Use convertor to convert from NV12 to RGBA as required by nvosd
    convert_pre_osd = make_elm_or_print_err(
        "nvvideoconvert", "convert_pre_osd", "Converter NV12->RGBA"
    )

    # OSD: to draw on the RGBA buffer
    nvosd = make_elm_or_print_err("nvdsosd", "onscreendisplay", "OSD (nvosd)")
    nvosd.set_property(
        "process-mode", 2
    )  # 0: CPU Mode, 1: GPU (only dGPU), 2: VIC (Jetson only)
    # nvosd.set_property("display-bbox", False)  # Bug: Removes all squares
    nvosd.set_property("display-clock", False)
    nvosd.set_property("display-text", True)  # Needed for any text

    # Finally encode and save the osd output
    queue = make_elm_or_print_err("queue", "queue", "Queue")
    convert_post_osd = make_elm_or_print_err(
        "nvvideoconvert", "convert_post_osd", "Converter RGBA->NV12"
    )

    # Video capabilities: check format and GPU/CPU location
    capsfilter = make_elm_or_print_err("capsfilter", "capsfilter", "capsfilter")
    if codec == CODEC_MP4:  # Not hw accelerated
        caps = Gst.Caps.from_string("video/x-raw, format=I420")
    else:  # hw accelerated
        caps = Gst.Caps.from_string("video/x-raw(memory:NVMM), format=I420")
    capsfilter.set_property("caps", caps)

    # Encoder: H265 has more efficient compression
    if codec == CODEC_MP4:
        print("Creating MPEG-4 stream")
        encoder = make_elm_or_print_err("avenc_mpeg4", "encoder", "Encoder")
        codeparser = make_elm_or_print_err(
            "mpeg4videoparse", "mpeg4-parser", "Code Parser"
        )
        rtppay = make_elm_or_print_err("rtpmp4vpay", "rtppay", "RTP MPEG-44 Payload")
    elif codec == CODEC_H264:
        print("Creating H264 stream")
        encoder = make_elm_or_print_err("nvv4l2h264enc", "encoder", "Encoder")
        encoder.set_property("preset-level", 1)
        encoder.set_property("bufapi-version", 1)
        codeparser = make_elm_or_print_err("h264parse", "h264-parser", "Code Parser")
        rtppay = make_elm_or_print_err("rtph264pay", "rtppay", "RTP H264 Payload")
    else:  # Default: H265 (recommended)
        print("Creating H265 stream")
        encoder = make_elm_or_print_err("nvv4l2h265enc", "encoder", "Encoder")
        encoder.set_property("preset-level", 1)
        encoder.set_property("bufapi-version", 1)
        codeparser = make_elm_or_print_err("h265parse", "h265-parser", "Code Parser")
        rtppay = make_elm_or_print_err("rtph265pay", "rtppay", "RTP H265 Payload")

    encoder.set_property("insert-sps-pps", 1)
    encoder.set_property("bitrate", output_bitrate)

    splitter_file_udp = make_elm_or_print_err(
        "tee", "tee_file_udp", "Splitter file/UDP"
    )

    # UDP streaming
    queue_udp = make_elm_or_print_err("queue", "queue_udp", "UDP queue")
    udpsink = make_elm_or_print_err("udpsink", "udpsink", "UDP Sink")
    udpsink.set_property("host", "224.224.255.255")
    udpsink.set_property("port", udp_port)
    udpsink.set_property("async", False)
    udpsink.set_property("sync", True)

    if output_filename is not None:
        queue_file = make_elm_or_print_err("queue", "queue_file", "File save queue")
        # codeparser already created above depending on codec
        container = make_elm_or_print_err("qtmux", "qtmux", "Container")
        filesink = make_elm_or_print_err("filesink", "filesink", "File Sink")
        filesink.set_property("location", output_filename)
    else:  # Fake sink, no save
        fakesink = make_elm_or_print_err("fakesink", "fakesink", "Fake Sink")

    # Add elements to the pipeline
    if camera_input:
        pipeline.add(source)
        pipeline.add(caps_camera)
        pipeline.add(vidconvsrc)
        pipeline.add(nvvidconvsrc)
        pipeline.add(caps_vidconvsrc)
    else:
        pipeline.add(source_bin)
    pipeline.add(streammux)
    pipeline.add(pgie)

    pipeline.add(convert_pre_osd)
    pipeline.add(nvosd)
    pipeline.add(queue)
    pipeline.add(convert_post_osd)
    pipeline.add(capsfilter)
    pipeline.add(encoder)
    pipeline.add(splitter_file_udp)

    if output_filename is not None:
        pipeline.add(queue_file)
        pipeline.add(codeparser)
        pipeline.add(container)
        pipeline.add(filesink)
    else:
        pipeline.add(fakesink)

    # Output to UDP
    pipeline.add(queue_udp)
    pipeline.add(rtppay)
    pipeline.add(udpsink)

    print("Linking elements in the Pipeline \n")

    # Pipeline Links
    if camera_input:
        source.link(caps_camera)
        caps_camera.link(vidconvsrc)
        vidconvsrc.link(nvvidconvsrc)
        nvvidconvsrc.link(caps_vidconvsrc)
        srcpad = caps_vidconvsrc.get_static_pad("src")
    else:
        srcpad = source_bin.get_static_pad("src")
    sinkpad = streammux.get_request_pad("sink_0")
    if not srcpad or not sinkpad:
        sys.stderr.write(" Unable to get file source or mux sink pads \n")
    srcpad.link(sinkpad)
    streammux.link(pgie)
    pgie.link(convert_pre_osd)
    convert_pre_osd.link(nvosd)
    nvosd.link(queue)
    queue.link(convert_post_osd)
    convert_post_osd.link(capsfilter)
    capsfilter.link(encoder)
    encoder.link(splitter_file_udp)

    # Split stream to file and rtsp
    tee_file = splitter_file_udp.get_request_pad("src_%u")
    tee_udp = splitter_file_udp.get_request_pad("src_%u")

    # Output to File or fake sinks
    if output_filename is not None:
        tee_file.link(queue_file.get_static_pad("sink"))
        queue_file.link(codeparser)
        codeparser.link(container)
        container.link(filesink)
    else:
        tee_file.link(fakesink.get_static_pad("sink"))

    # Output to UDP
    tee_udp.link(queue_udp.get_static_pad("sink"))
    queue_udp.link(rtppay)
    rtppay.link(udpsink)

    # Lets add probe to get informed of the meta data generated, we add probe to
    # the sink pad of the osd element, since by that time, the buffer would have
    # had got all the metadata.
    osdsinkpad = nvosd.get_static_pad("sink")
    if not osdsinkpad:
        sys.stderr.write(" Unable to get sink pad of nvosd \n")

    osdsinkpad.add_probe(Gst.PadProbeType.BUFFER, osd_sink_pad_buffer_probe, 0)

    # GLib loop required for RTSP server
    g_loop = GLib.MainLoop()
    g_context = g_loop.get_context()

    # GStreamer message bus
    bus = pipeline.get_bus()

    if e_external_interrupt is None:
        # Use threading instead of mp.Event() for sigint_handler, see:
        # https://bugs.python.org/issue41606
        e_interrupt = threading.Event()
        signal.signal(signal.SIGINT, sigint_handler)
        print("[green bold]Press Ctrl+C to stop pipeline[/green bold]")
    else:
        # If there's an external interrupt, don't capture SIGINT
        e_interrupt = e_external_interrupt

    # start play back and listen to events
    pipeline.set_state(Gst.State.PLAYING)

    # After setting pipeline to PLAYING, stop it even on exceptions
    try:
        time_start_playing = time.time()

        if mqtt_client is not None:
            cb_args = mqtt_send_period
            GLib.timeout_add_seconds(mqtt_send_period, cb_send_statistics, cb_args)

        # Custom event loop
        running = True
        while running:
            g_context.iteration(may_block=False)

            message = bus.pop()
            if message is not None:
                t = message.type

                if t == Gst.MessageType.EOS:
                    print("End-of-stream\n")
                    running = False
                elif t == Gst.MessageType.WARNING:
                    err, debug = message.parse_warning()
                    console.log(f"[yellow]WARNING[/yellow] {err}: {debug}\n")
                elif t == Gst.MessageType.ERROR:
                    err, debug = message.parse_error()
                    console.log(f"[red]ERROR [/red] {err}: {debug}\n")
                    show_troubleshooting()
                    running = False
                else:
                    # 100ms pause if no messages, only affects termination
                    time.sleep(100e-3)
            if e_interrupt.is_set():
                # Send EOS to container to generate a valid mp4 file
                if output_filename is not None:
                    container.send_event(Gst.Event.new_eos())
                    udpsink.send_event(Gst.Event.new_eos())
                else:
                    pipeline.send_event(Gst.Event.new_eos())  # fakesink EOS won't work

        end_time = time.time()
        print("Inference main loop ending.")
        pipeline.set_state(Gst.State.NULL)

        # Profiling display
        if start_time is not None and end_time is not None:
            total_time = end_time - start_time
            total_frames = (
                total_frames - 1
            )  # Remove first frame as its inference is not counted
            inference_frames = total_frames // (inference_interval + 1)
            print(f"\n[bold yellow] ---- Profiling ---- [/bold yellow]")
            print(
                f"Inference frames: {inference_frames} | Processed frames: {total_frames}"
            )
            print(
                f"Time from time_start_playing: {end_time - time_start_playing:.2f} seconds"
            )
            print(f"Total time skipping first inference: {total_time:.2f} seconds")
            print(f"Avg. time/frame: {total_time/total_frames:.4f} secs")
            print(
                f"[bold yellow]FPS: {total_frames/total_time:.1f} frames/second[/bold yellow]\n"
            )
            if inference_interval != 0:
                print(
                    f"[red]WARNING:[/red] skipping inference every interval={inference_interval} frames"
                )
        if output_filename is not None:
            print(f"Output file saved: [green bold]{output_filename}[/green bold]")
    except:
        console.print_exception()
        pipeline.set_state(Gst.State.NULL)


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    config.sections()

    # Check input arguments
    output_filename = None
    if len(sys.argv) > 1:
        input_filename = sys.argv[1]
        print(f"Provided input source: {input_filename}")
        if len(sys.argv) > 2:
            output_filename = sys.argv[2]
            print(f"Save output file: [green]{output_filename}[/green]")
    else:
        input_filename = config["maskcam"]["default-input"]
        print(f"Using input from config file: {input_filename}")

    sys.exit(
        main(
            config=config,
            input_filename=input_filename,
            output_filename=output_filename,
        )
    )

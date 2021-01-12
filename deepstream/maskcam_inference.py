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

import gi
import pyds
import sys
import ipdb
import time
import signal
import platform
import configparser
import numpy as np

gi.require_version("Gst", "1.0")
gi.require_version("GstRtspServer", "1.0")
from gi.repository import GLib, Gst, GstRtspServer

sys.path.append("../../norfair")
sys.path.append("../../filterpy")
from norfair.tracker import Tracker, Detection

# See ../yolo/data/obj.names
PGIE_CLASS_ID_MASK = 0
PGIE_CLASS_ID_NO_MASK = 1
PGIE_CLASS_ID_NOT_VISIBLE = 2
PGIE_CLASS_ID_MISPLACED = 3
frame_number = 0
start_time = None
end_time = None
total_frames = 0
sigint_received = False

CODEC_MP4 = "MP4"
CODEC_H265 = "H265"
CODEC_H264 = "H264"


class FaceMask:
    def __init__(self, th_detection, th_vote, min_face_size):
        self.people_votes = {}
        self.th_detection = th_detection
        self.th_vote = th_vote
        self.min_face_size = min_face_size
        self.min_votes = 10
        self.color_mask = (0.0, 1.0, 0.0)  # green
        self.color_no_mask = (1.0, 0.0, 0.0)  # red
        self.color_unknown = (1.0, 1.0, 0.0)  # yellow
        self.draw_raw_detections = False
        self.draw_tracked_people = True

    def validate_detection(self, box_points, score, label):
        box_width = box_points[1][0] - box_points[0][0]
        box_height = box_points[1][1] - box_points[0][1]
        return (
            min(box_width, box_height) >= self.min_face_size
            and score >= self.th_detection
        )

    def add_detection(self, person_id, label, score):
        if person_id not in self.people_votes:
            self.people_votes[person_id] = 0
        if score > self.th_vote:
            if label == "mask":
                self.people_votes[person_id] += 1
            elif label == "no_mask" or "misplaced":
                self.people_votes[person_id] -= 1

    def get_person_label(self, person_id):
        person_votes = self.people_votes[person_id]
        if abs(person_votes) >= self.min_votes:
            color = self.color_mask if person_votes > 0 else self.color_no_mask
            label = "mask" if person_votes > 0 else "no mask"
        else:
            color = self.color_unknown
            label = "not visible"
        return f"{person_id}|{label}({abs(person_votes)})", color


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


face_mask = FaceMask(0.3, 0.9, 32)

# In Norfair we trust
tracker = Tracker(
    distance_function=keypoints_distance,
    detection_threshold=face_mask.th_detection,
    distance_threshold=1,
    point_transience=8,
    hit_inertia_min=25,
    hit_inertia_max=60,
)


def handle_interrupt(sig, frame):
    global sigint_received
    sigint_received = True


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
        print("Unable to get GstBuffer ")
        return

    # Retrieve batch metadata from the gst_buffer
    # Note that pyds.gst_buffer_get_nvds_batch_meta() expects the
    # C address of gst_buffer as input, which is obtained with hash(gst_buffer)
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    if not total_frames % 30:
        print(f"Processed {total_frames} frames...")

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

        tracked_people = tracker.update(detections)

        # Filter out people with no live points (don't draw)
        drawn_people = [person for person in tracked_people if person.live_points.any()]

        # Each meta object carries max 16 rects/labels/etc.
        max_drawings_per_meta = 16  # This is hardcoded, not documented

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
                    display_meta = pyds.nvds_acquire_display_meta_from_pool(batch_meta)
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
    print("Decodebin child added:", name, "\n")
    if name.find("decodebin") != -1:
        Object.connect("child-added", decodebin_child_added, user_data)
    if is_aarch64() and name.find("nvv4l2decoder") != -1:
        print("Seting bufapi_version\n")
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


def make_elm_or_print_err(factoryname, name, printedname, detail=""):
    """Creates an element with Gst Element Factory make.
    Return the element  if successfully created, otherwise print
    to stderr and return None.
    """
    print("Creating", printedname)
    elm = Gst.ElementFactory.make(factoryname, name)
    if not elm:
        sys.stderr.write("Unable to create " + printedname + " \n")
        if detail:
            sys.stderr.write(detail)
    return elm


def set_nvtracker_configuration(tracker, config_file):
    # Set properties of tracker
    config = configparser.ConfigParser()
    config.read(config_file)
    config.sections()

    for key in config["tracker"]:
        if key == "tracker-width":
            tracker_width = config.getint("tracker", key)
            tracker.set_property("tracker-width", tracker_width)
        if key == "tracker-height":
            tracker_height = config.getint("tracker", key)
            tracker.set_property("tracker-height", tracker_height)
        if key == "gpu-id":
            tracker_gpu_id = config.getint("tracker", key)
            tracker.set_property("gpu_id", tracker_gpu_id)
        if key == "ll-lib-file":
            tracker_ll_lib_file = config.get("tracker", key)
            tracker.set_property("ll-lib-file", tracker_ll_lib_file)
        if key == "ll-config-file":
            tracker_ll_config_file = config.get("tracker", key)
            tracker.set_property("ll-config-file", tracker_ll_config_file)
        if key == "enable-batch-process":
            tracker_enable_batch_process = config.getint("tracker", key)
            tracker.set_property("enable_batch_process", tracker_enable_batch_process)


def main(args):
    global frame_number
    global total_frames
    global start_time
    global end_time
    global sigint_received

    config = configparser.ConfigParser()
    config_file = "config_maskcam.txt"  # Also used in nvinfer element
    config.read(config_file)
    config.sections()
    udp_port = int(config["maskcam"]["udp-port"])
    codec = config["maskcam"]["codec"]
    inference_interval = int(config["property"]["interval"])

    # Check input arguments
    camera_protocol = "camera://"  # Invented by us since there's no URI for this
    if len(args) != 2:
        input_filename = config["maskcam"]["default-input"]
        print(f"Using input from config file: {input_filename}")
    else:
        input_filename = args[1]
        print(f"Provided input source: {input_filename}")

    nvtracker_enabled = False  # Using Norfair
    config_nvtracker = "config_nvtracker.txt"

    # Input camera configuration
    # Use ./gst_capabilities.sh to get the list of available capabilities from /dev/video0
    input_width = 1024
    input_height = 576
    camera_capabilities = (
        f"video/x-raw, framerate=10/1, width={input_width}, height={input_height}"
    )

    # Original: 1920x1080, bdti_resized: 1024x576, yolo-input: 1024x608
    output_width = 1920
    output_height = 1080
    output_bitrate = 4000000  # Nice for h264@1024x576: 4000000

    print(f"Playing file {input_filename}")
    print(f"Output codec: {codec}")

    # Standard GStreamer initialization
    # GObject.threads_init()  # Doesn't seem necessary (see https://pygobject.readthedocs.io/en/latest/guide/threading.html)
    Gst.init(None)

    # Create gstreamer elements
    # Create Pipeline element that will form a connection of other elements
    print("Creating Pipeline \n ")
    pipeline = Gst.Pipeline()

    if not pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")

    # On Jetson, there is a problem with the encoder failing to initialize
    # due to limitation on TLS usage. To work around this, preload libgomp.
    # Add a reminder here in case the user forgets.
    preload_reminder = (
        "If the following error is encountered:\n"
        + "/usr/lib/aarch64-linux-gnu/libgomp.so.1: cannot allocate memory in static TLS block\n"
        + "Preload the offending library:\n"
        + "export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1\n"
    )

    camera_input = camera_protocol in input_filename
    if camera_input:
        input_device = input_filename[len(camera_protocol) :]
        print(f"Reading from camera device: {input_device}")

        source = make_elm_or_print_err("v4l2src", "v4l2-camera-source", "Camera input")
        source.set_property("device", input_device)

        # Misterious converting sequence from deepstream_test_1_usb.py
        caps_v4l2src = make_elm_or_print_err(
            "capsfilter", "v4l2src_caps", "v4lsrc caps filter"
        )
        caps_v4l2src.set_property(
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

    # Inference element: object detection using TRT engine
    pgie = make_elm_or_print_err("nvinfer", "primary-inference", "pgie")
    pgie.set_property("config-file-path", config_file)

    # Tracker by nvidia (not used, kept just in case)
    if nvtracker_enabled:
        tracker = make_elm_or_print_err("nvtracker", "tracker", "Tracker")
        set_nvtracker_configuration(tracker, config_nvtracker)

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
        encoder = make_elm_or_print_err(
            "avenc_mpeg4", "encoder", "Encoder", preload_reminder
        )
        rtppay = make_elm_or_print_err("rtpmp4vpay", "rtppay", "RTP MPEG-44 Payload")
    elif codec == CODEC_H264:
        print("Creating H264 stream")
        encoder = make_elm_or_print_err(
            "nvv4l2h264enc", "encoder", "Encoder", preload_reminder
        )
        rtppay = make_elm_or_print_err("rtph264pay", "rtppay", "RTP H264 Payload")
    else:  # Default: H265 (recommended)
        print("Creating H265 stream")
        encoder = make_elm_or_print_err(
            "nvv4l2h265enc", "encoder", "Encoder", preload_reminder
        )
        rtppay = make_elm_or_print_err("rtph265pay", "rtppay", "RTP H265 Payload")

    encoder.set_property("bitrate", output_bitrate)
    # Taken from test1_rtsp_out python sample app
    # Works without this, and it's not documented, keep an eye on this
    encoder.set_property("preset-level", 1)
    encoder.set_property("insert-sps-pps", 1)
    encoder.set_property("bufapi-version", 1)

    # UDP streaming
    queue_udp = make_elm_or_print_err("queue", "queue_udp", "UDP queue")
    udpsink = make_elm_or_print_err("udpsink", "udpsink", "UDP Sink")
    udpsink.set_property("host", "224.224.255.255")
    udpsink.set_property("port", udp_port)
    udpsink.set_property("async", False)
    udpsink.set_property("sync", 1)

    # Add elements to the pipeline
    if camera_input:
        pipeline.add(source)
        pipeline.add(caps_v4l2src)
        pipeline.add(vidconvsrc)
        pipeline.add(nvvidconvsrc)
        pipeline.add(caps_vidconvsrc)
    else:
        pipeline.add(source_bin)
    pipeline.add(streammux)
    pipeline.add(pgie)
    if nvtracker_enabled:
        pipeline.add(tracker)

    pipeline.add(convert_pre_osd)
    pipeline.add(nvosd)
    pipeline.add(queue)
    pipeline.add(convert_post_osd)
    pipeline.add(capsfilter)
    pipeline.add(encoder)

    # Output to UDP
    pipeline.add(queue_udp)
    pipeline.add(rtppay)
    pipeline.add(udpsink)

    print("Linking elements in the Pipeline \n")

    # Pipeline Links
    if camera_input:
        source.link(caps_v4l2src)
        caps_v4l2src.link(vidconvsrc)
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
    if nvtracker_enabled:
        pgie.link(tracker)
        tracker.link(convert_pre_osd)
    else:
        pgie.link(convert_pre_osd)
    convert_pre_osd.link(nvosd)
    nvosd.link(queue)
    queue.link(convert_post_osd)
    convert_post_osd.link(capsfilter)
    capsfilter.link(encoder)
    encoder.link(queue_udp)

    # Output to UDP
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

    # start play back and listen to events
    print("Starting pipeline. Press Ctrl+C to stop processing")
    pipeline.set_state(Gst.State.PLAYING)
    time_start_playing = time.time()

    try:
        g_loop.run()
    except KeyboardInterrupt:
        print("Keyboard interruption received")

    end_time = time.time()
    print("Finished processing")
    pipeline.set_state(Gst.State.NULL)

    # Profiling display
    if start_time is not None and end_time is not None:
        total_time = end_time - start_time
        total_frames = (
            total_frames - 1
        )  # Remove first frame as its inference is not counted
        inference_frames = total_frames // (inference_interval + 1)
        print(f" ---- Profiling ---- ")
        print(
            f"Inference frames: {inference_frames} | Processed frames: {total_frames}"
        )
        print(
            f"Time from time_start_playing: {end_time - time_start_playing:.2f} seconds"
        )
        print(f"Total time skipping first inference: {total_time:.2f} seconds")
        print(f"Avg. time/frame: {total_time/total_frames:.4f} secs")
        print(f"FPS: {total_frames/total_time:.1f} frames/second")
        if inference_interval != 0:
            print(
                f"WARNING: skipping inference every interval={inference_interval} frames"
            )


if __name__ == "__main__":
    sys.exit(main(sys.argv))

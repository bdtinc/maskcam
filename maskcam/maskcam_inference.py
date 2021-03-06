#!/usr/bin/env python3

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

import os
import gi
import pyds
import sys
import ipdb
import time
import signal
import platform
import threading
import numpy as np
import multiprocessing as mp
from rich.console import Console
from datetime import datetime, timezone


gi.require_version("Gst", "1.0")
gi.require_version("GstRtspServer", "1.0")
from gi.repository import GLib, Gst, GstRtspServer

from norfair.tracker import Tracker, Detection

from .config import config, print_config_overrides
from .prints import print_inference as print
from .common import (
    CODEC_MP4,
    CODEC_H264,
    CODEC_H265,
    USBCAM_PROTOCOL,
    RASPICAM_PROTOCOL,
    CONFIG_FILE,
)
from .utils import glib_cb_restart, load_udp_ports_filesaving


# YOLO labels. See obj.names file
LABEL_MASK = "mask"
LABEL_NO_MASK = "no_mask"  # YOLOv4: no_mask
LABEL_MISPLACED = "misplaced"
LABEL_NOT_VISIBLE = "not_visible"
FRAMES_LOG_INTERVAL = int(config["maskcam"]["inference-log-interval"])

# Global vars
frame_number = 0
start_time = None
end_time = None
console = Console()
e_interrupt = None


class FaceMaskProcessor:
    def __init__(
        self, th_detection=0, th_vote=0, min_face_size=0, tracker_period=1, disable_tracker=False
    ):
        self.people_votes = {}
        self.current_people = set()
        self.th_detection = th_detection
        self.th_vote = th_vote
        self.tracker_period = tracker_period
        self.min_face_size = min_face_size
        self.disable_detection_validation = False
        self.min_votes = 5
        self.max_votes = 50
        self.color_mask = (0.0, 1.0, 0.0)  # green
        self.color_no_mask = (1.0, 0.0, 0.0)  # red
        self.color_unknown = (1.0, 1.0, 0.0)  # yellow
        self.draw_raw_detections = disable_tracker
        self.draw_tracked_people = not disable_tracker
        self.stats_lock = threading.Lock()

        # Norfair Tracker
        if disable_tracker:
            self.tracker = None
        else:
            self.tracker = Tracker(
                distance_function=self.keypoints_distance,
                detection_threshold=self.th_detection,
                distance_threshold=1,
                point_transience=8,
                hit_inertia_min=15,
                hit_inertia_max=45,
            )

    def keypoints_distance(self, detected_pose, tracked_pose):
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

    def validate_detection(self, box_points, score, label):
        if self.disable_detection_validation:
            return True
        box_width = box_points[1][0] - box_points[0][0]
        box_height = box_points[1][1] - box_points[0][1]
        return min(box_width, box_height) >= self.min_face_size and score >= self.th_detection

    def add_detection(self, person_id, label, score):
        # This function is called from streaming thread
        with self.stats_lock:
            self.current_people.add(person_id)
            if person_id not in self.people_votes:
                self.people_votes[person_id] = 0
            if score > self.th_vote:
                if label == LABEL_MASK:
                    self.people_votes[person_id] += 1
                elif label == LABEL_NO_MASK or LABEL_MISPLACED:
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
                    id: votes for id, votes in self.people_votes.items() if id in filter_ids
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


def cb_add_statistics(cb_args):
    stats_period, stats_queue, face_processor = cb_args

    people_total, people_classified, people_mask = face_processor.get_instant_statistics(
        refresh=True
    )
    people_no_mask = people_classified - people_mask

    # stats_queue is an mp.Queue optionally provided externally (in main())
    stats_queue.put_nowait(
        {
            "people_total": people_total,
            "people_with_mask": people_mask,
            "people_without_mask": people_no_mask,
            "timestamp": datetime.timestamp(datetime.now(timezone.utc)),
        }
    )

    # Next report timeout
    GLib.timeout_add_seconds(stats_period, cb_add_statistics, cb_args)


def sigint_handler(sig, frame):
    # This function is not used if e_external_interrupt is provided
    print("[red]Ctrl+C pressed. Interrupting inference...[/red]")
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


def cb_buffer_probe(pad, info, cb_args):
    global frame_number
    global start_time

    face_processor, e_ready = cb_args
    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer", error=True)
        return

    # Set e_ready event to notify the pipeline is working (e.g: for orchestrator)
    if e_ready is not None and not e_ready.is_set():
        print("Inference pipeline setting [green]e_ready[/green]")
        e_ready.set()

    # Retrieve batch metadata from the gst_buffer
    # Note that pyds.gst_buffer_get_nvds_batch_meta() expects the
    # C address of gst_buffer as input, which is obtained with hash(gst_buffer)
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))

    l_frame = batch_meta.frame_meta_list
    while l_frame is not None:
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
            obj_meta.rect_params.border_color.set(0.0, 0.0, 1.0, 0.0)
            box = obj_meta.rect_params
            # print(f"{obj_meta.obj_label} | {obj_meta.confidence}")

            box_points = (
                (box.left, box.top),
                (box.left + box.width, box.top + box.height),
            )
            box_p = obj_meta.confidence
            box_label = obj_meta.obj_label
            if face_processor.validate_detection(box_points, box_p, box_label):
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

        if face_processor.tracker is not None:
            # Track, count and draw tracked people
            tracked_people = face_processor.tracker.update(
                detections, period=face_processor.tracker_period
            )
            # Filter out people with no live points (don't draw)
            drawn_people = [person for person in tracked_people if person.live_points.any()]

            if face_processor.draw_tracked_people:
                for n_person, person in enumerate(drawn_people):
                    points = person.estimate
                    box_points = points.clip(0).astype(int)

                    # Update mask votes
                    face_processor.add_detection(
                        person.id,
                        person.last_detection.data["label"],
                        person.last_detection.data["p"],
                    )
                    label, color = face_processor.get_person_label(person.id)

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
        if face_processor.draw_raw_detections:
            for n_detection, detection in enumerate(detections):
                points = detection.points
                box_points = points.clip(0).astype(int)
                label = detection.data["label"]
                if label == LABEL_MASK:
                    color = face_processor.color_mask
                elif label == LABEL_NO_MASK or label == LABEL_MISPLACED:
                    color = face_processor.color_no_mask
                else:
                    color = face_processor.color_unknown
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
        if not frame_number % FRAMES_LOG_INTERVAL:
            print(f"Processed {frame_number} frames...")

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
                print("Failed to link decoder src pad to source bin ghost pad", error=True)
        else:
            print("Decodebin did not pick nvidia decoder plugin", error=True)


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
        print("Unable to create source bin", error=True)

    # Source element for reading from the uri.
    # We will use decodebin and let it figure out the container format of the
    # stream and the codec and plug the appropriate demux and decode plugins.
    uri_decode_bin = Gst.ElementFactory.make("uridecodebin", "uri-decode-bin")
    if not uri_decode_bin:
        print("Unable to create uri decode bin", error=True)
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
        print("Failed to add ghost pad in source bin", error=True)
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
        print("Unable to create ", printedname, error=True)
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
    Run the script under utils/gst_capabilities.sh and find the lines with type
    video/x-raw ...
    Find a suitable framerate=X/1 (with X being an integer like 24, 15, etc.)
    Then edit config_maskcam.txt and change the line:
    camera-framerate=X
    Or configure using --env MASKCAM_CAMERA_FRAMERATE=X (see README)

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
    stats_queue: mp.Queue = None,
    e_ready: mp.Event = None,
):
    global frame_number
    global start_time
    global end_time
    global e_interrupt

    # Load all udp ports to output video
    udp_ports = {int(config["maskcam"]["udp-port-streaming"])}
    load_udp_ports_filesaving(config, udp_ports)

    codec = config["maskcam"]["codec"]
    stats_period = int(config["maskcam"]["statistics-period"])

    # Original: 1920x1080, bdti_resized: 1024x576, yolo-input: 1024x608
    output_width = int(config["maskcam"]["output-video-width"])
    output_height = int(config["maskcam"]["output-video-height"])
    output_bitrate = 6000000  # Nice for h264@1024x576: 4000000

    # Two types of camera supported: USB or Raspi
    usbcam_input = USBCAM_PROTOCOL in input_filename
    raspicam_input = RASPICAM_PROTOCOL in input_filename
    camera_input = usbcam_input or raspicam_input
    if camera_input:
        camera_framerate = int(config["maskcam"]["camera-framerate"])
        camera_flip_method = int(config["maskcam"]["camera-flip-method"])

    # Set nvinfer.interval (number of frames to skip inference and use tracker instead)
    if camera_input and int(config["maskcam"]["inference-interval-auto"]):
        max_fps = int(config["maskcam"]["inference-max-fps"])
        skip_inference = camera_framerate // max_fps
        print(f"Auto calculated frames to skip inference: {skip_inference}")
    else:
        skip_inference = int(config["property"]["interval"])
        print(f"Configured frames to skip inference: {skip_inference}")

    # FaceMask initialization
    face_tracker_period = skip_inference + 1  # tracker_period=skipped + inference frame(1)
    face_detection_threshold = float(config["face-processor"]["detection-threshold"])
    face_voting_threshold = float(config["face-processor"]["voting-threshold"])
    face_min_face_size = int(config["face-processor"]["min-face-size"])
    face_disable_tracker = int(config["face-processor"]["disable-tracker"])
    face_processor = FaceMaskProcessor(
        th_detection=face_detection_threshold,
        th_vote=face_voting_threshold,
        min_face_size=face_min_face_size,
        tracker_period=face_tracker_period,
        disable_tracker=face_disable_tracker,
    )

    # Standard GStreamer initialization
    Gst.init(None)

    # Create gstreamer elements
    # Create Pipeline element that will form a connection of other elements
    print("Creating Pipeline \n ")
    pipeline = Gst.Pipeline()

    if not pipeline:
        print("Unable to create Pipeline", error=True)

    if camera_input:
        if usbcam_input:
            input_device = input_filename[len(USBCAM_PROTOCOL) :]
            source = make_elm_or_print_err("v4l2src", "v4l2-camera-source", "Camera input")
            source.set_property("device", input_device)
            nvvidconvsrc = make_elm_or_print_err(
                "nvvideoconvert", "convertor_src2", "Convertor src 2"
            )

            # Input camera configuration
            # Use ./gst_capabilities.sh to get the list of available capabilities from /dev/video0
            camera_capabilities = f"video/x-raw, framerate={camera_framerate}/1"
        elif raspicam_input:
            input_device = input_filename[len(RASPICAM_PROTOCOL) :]
            source = make_elm_or_print_err(
                "nvarguscamerasrc", "nv-argus-camera-source", "RaspiCam input"
            )
            source.set_property("sensor-id", int(input_device))
            source.set_property("bufapi-version", 1)

            # Special camera_capabilities for raspicam
            camera_capabilities = f"video/x-raw(memory:NVMM),framerate={camera_framerate}/1"
            nvvidconvsrc = make_elm_or_print_err("nvvidconv", "convertor_flip", "Convertor flip")
            nvvidconvsrc.set_property("flip-method", camera_flip_method)

        # Misterious converting sequence from deepstream_test_1_usb.py
        caps_camera = make_elm_or_print_err("capsfilter", "camera_src_caps", "Camera caps filter")
        caps_camera.set_property(
            "caps",
            Gst.Caps.from_string(camera_capabilities),
        )
        vidconvsrc = make_elm_or_print_err("videoconvert", "convertor_src1", "Convertor src 1")
        caps_vidconvsrc = make_elm_or_print_err(
            "capsfilter", "nvmm_caps", "NVMM caps for input stream"
        )
        caps_vidconvsrc.set_property("caps", Gst.Caps.from_string("video/x-raw(memory:NVMM)"))
    else:
        source_bin = create_source_bin(0, input_filename)

    # Create nvstreammux instance to form batches from one or more sources.
    streammux = make_elm_or_print_err("nvstreammux", "Stream-muxer", "NvStreamMux")
    streammux.set_property("width", output_width)
    streammux.set_property("height", output_height)
    streammux.set_property("enable-padding", True)  # Keeps aspect ratio, but adds black margin
    streammux.set_property("batch-size", 1)
    streammux.set_property("batched-push-timeout", 4000000)

    # Adding this element after muxer will cause detections to get delayed
    # videorate = make_elm_or_print_err("videorate", "Vide-rate", "Video Rate")

    # Inference element: object detection using TRT engine
    pgie = make_elm_or_print_err("nvinfer", "primary-inference", "pgie")
    pgie.set_property("config-file-path", CONFIG_FILE)
    pgie.set_property("interval", skip_inference)

    # Use convertor to convert from NV12 to RGBA as required by nvosd
    convert_pre_osd = make_elm_or_print_err(
        "nvvideoconvert", "convert_pre_osd", "Converter NV12->RGBA"
    )

    # OSD: to draw on the RGBA buffer
    nvosd = make_elm_or_print_err("nvdsosd", "onscreendisplay", "OSD (nvosd)")
    nvosd.set_property("process-mode", 2)  # 0: CPU Mode, 1: GPU (only dGPU), 2: VIC (Jetson only)
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
        codeparser = make_elm_or_print_err("mpeg4videoparse", "mpeg4-parser", "Code Parser")
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

    splitter_file_udp = make_elm_or_print_err("tee", "tee_file_udp", "Splitter file/UDP")

    # UDP streaming
    queue_udp = make_elm_or_print_err("queue", "queue_udp", "UDP queue")
    multiudpsink = make_elm_or_print_err("multiudpsink", "multi udpsink", "Multi UDP Sink")
    # udpsink.set_property("host", "127.0.0.1")
    # udpsink.set_property("port", udp_port)

    # Comma separated list of clients, don't add spaces :S
    client_list = [f"127.0.0.1:{udp_port}" for udp_port in udp_ports]
    multiudpsink.set_property("clients", ",".join(client_list))

    multiudpsink.set_property("async", False)
    multiudpsink.set_property("sync", True)

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
    pipeline.add(multiudpsink)

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
        print("Unable to get file source or mux sink pads", error=True)
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
    rtppay.link(multiudpsink)

    # Lets add probe to get informed of the meta data generated, we add probe to
    # the sink pad of the osd element, since by that time, the buffer would have
    # had got all the metadata.
    osdsinkpad = nvosd.get_static_pad("sink")
    if not osdsinkpad:
        print("Unable to get sink pad of nvosd", error=True)

    cb_args = (face_processor, e_ready)
    osdsinkpad.add_probe(Gst.PadProbeType.BUFFER, cb_buffer_probe, cb_args)

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

        # Timer to add statistics to queue
        if stats_queue is not None:
            cb_args = stats_period, stats_queue, face_processor
            GLib.timeout_add_seconds(stats_period, cb_add_statistics, cb_args)

        # Periodic gloop interrupt (see utils.glib_cb_restart)
        t_check = 100
        GLib.timeout_add(t_check, glib_cb_restart, t_check)

        # Custom event loop
        running = True
        while running:
            g_context.iteration(may_block=True)

            message = bus.pop()
            if message is not None:
                t = message.type

                if t == Gst.MessageType.EOS:
                    print("End-of-stream\n")
                    running = False
                elif t == Gst.MessageType.WARNING:
                    err, debug = message.parse_warning()
                    print(f"{err}: {debug}", warning=True)
                elif t == Gst.MessageType.ERROR:
                    err, debug = message.parse_error()
                    print(f"{err}: {debug}", error=True)
                    show_troubleshooting()
                    running = False
            if e_interrupt.is_set():
                # Send EOS to container to generate a valid mp4 file
                if output_filename is not None:
                    container.send_event(Gst.Event.new_eos())
                    multiudpsink.send_event(Gst.Event.new_eos())
                else:
                    pipeline.send_event(Gst.Event.new_eos())  # fakesink EOS won't work

        end_time = time.time()
        print("Inference main loop ending.")
        pipeline.set_state(Gst.State.NULL)

        # Profiling display
        if start_time is not None and end_time is not None:
            total_time = end_time - start_time
            total_frames = frame_number
            inference_frames = total_frames // (skip_inference + 1)
            print()
            print(f"[bold yellow] ---- Profiling ---- [/bold yellow]")
            print(f"Inference frames: {inference_frames} | Processed frames: {total_frames}")
            print(f"Time from time_start_playing: {end_time - time_start_playing:.2f} seconds")
            print(f"Total time skipping first inference: {total_time:.2f} seconds")
            print(f"Avg. time/frame: {total_time/total_frames:.4f} secs")
            print(f"[bold yellow]FPS: {total_frames/total_time:.1f} frames/second[/bold yellow]\n")
            if skip_inference != 0:
                print(
                    "[red]NOTE: FPS calculated skipping inference every"
                    f" interval={skip_inference} frames[/red]"
                )
        if output_filename is not None:
            print(f"Output file saved: [green bold]{output_filename}[/green bold]")
    except:
        console.print_exception()
        pipeline.set_state(Gst.State.NULL)


if __name__ == "__main__":
    print_config_overrides()
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

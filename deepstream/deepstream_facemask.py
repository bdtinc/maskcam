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
import platform
import configparser
import numpy as np

gi.require_version("Gst", "1.0")
gi.require_version("GstRtspServer", "1.0")
from gi.repository import Gst, GstRtspServer

sys.path.append("../../norfair")
sys.path.append("../../filterpy")
from norfair.tracker import Tracker, Detection

# See ../yolo/data/obj.names
PGIE_CLASS_ID_MASK = 0
PGIE_CLASS_ID_NO_MASK = 1
PGIE_CLASS_ID_NOT_VISIBLE = 2
PGIE_CLASS_ID_MISPLACED = 3
frame_number = 0

CODEC_MP4 = "MP4"
CODEC_H265 = "H265"
CODEC_H264 = "H264"


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


# In Norfair we trust
tracker = Tracker(
    distance_function=keypoints_distance,
    detection_threshold=0.5,
    distance_threshold=1,
    point_transience=1,
    hit_inertia_min=25,
    hit_inertia_max=60,
)


def is_aarch64():
    return platform.uname()[4] == "aarch64"


def osd_sink_pad_buffer_probe(pad, info, u_data):
    global frame_number
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
        if frame_number == 100:
            print("Processing frame 100")
        num_rects = frame_meta.num_obj_meta
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
            x1, y1, x2, y2 = (
                box.left,
                box.top,
                box.left + box.width,
                box.top + box.height,
            )
            detections.append(
                Detection(
                    np.array(((x1, y1), (x2, y2))),
                    data={"label": obj_meta.obj_label, "p": obj_meta.confidence},
                )
            )
            try:
                l_obj = l_obj.next
            except StopIteration:
                break

        # Remove all object meta to avoid drawing. Do this outside while since we're modifying list
        for obj_meta in obj_meta_list:
            # Remove this to avoid drawing label texts
            pyds.nvds_remove_obj_meta_from_frame(frame_meta, obj_meta)
        obj_meta_list = None
        print(f"Num dets: {len(detections)}")

        tracked_people = tracker.update(detections)

        # Acquiring a display meta object. The memory ownership remains in
        # the C code so downstream plugins can still access it. Otherwise
        # the garbage collector will claim it when this probe function exits.
        display_meta = pyds.nvds_acquire_display_meta_from_pool(batch_meta)
        # display_meta.num_labels = 1
        # py_nvosd_text_params = display_meta.text_params[0]
        # # Setting display text to be shown on screen
        # # Note that the pyds module allocates a buffer for the string, and the
        # # memory will not be claimed by the garbage collector.
        # # Reading the display_text field here will return the C address of the
        # # allocated string. Use pyds.get_string() to get the string content.
        # py_nvosd_text_params.display_text = "Frame Number={} Number of Objects={} With mask={} No mask/misplaced={}".format(
        #     frame_number,
        #     num_rects,
        #     obj_counter[PGIE_CLASS_ID_MASK],
        #     obj_counter[PGIE_CLASS_ID_NO_MASK] + obj_counter[PGIE_CLASS_ID_MISPLACED],
        # )

        # # Now set the offsets where the string should appear
        # py_nvosd_text_params.x_offset = 10
        # py_nvosd_text_params.y_offset = 12

        # # Font , font-color and font-size
        # py_nvosd_text_params.font_params.font_name = "Serif"
        # py_nvosd_text_params.font_params.font_size = 10
        # # set(red, green, blue, alpha); set to White
        # py_nvosd_text_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)

        # # Text background color
        # py_nvosd_text_params.set_bg_clr = 1
        # # set(red, green, blue, alpha); set to Black
        # py_nvosd_text_params.text_bg_clr.set(0.0, 0.0, 0.0, 1.0)

        # Delete all previous drawings from detector
        rect_n = 0  # display_meta.num_rects  # Just in case something was drawn before
        label_n = 0  # display_meta.num_labels
        for person in tracked_people:
            if not person.live_points.any():
                continue
            points = person.estimate
            rect = display_meta.rect_params[rect_n]
            ((x1, y1), (x2, y2)) = points.clip(0).astype(int)
            detection_label = person.last_detection.data["label"]
            detection_p = person.last_detection.data["p"]
            if detection_label == "mask":
                color = (0, 1.0, 0)
            elif detection_label == "no_mask":
                color = (1.0, 0, 0)
            else:
                color = (1.0, 1.0, 0)  # yellow
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
            label = display_meta.text_params[label_n]
            label.x_offset = x1
            label.y_offset = y2
            label.font_params.font_name = "Verdana"
            label.font_params.font_size = 9
            label.font_params.font_color.set(0, 0, 0, 1.0)
            label.display_text = f"{person.id} | {detection_p:.2f}"
            label.set_bg_clr = True
            label.text_bg_clr.set(*color, 0.5)
            rect_n += 1
            label_n += 1
        display_meta.num_rects = rect_n
        display_meta.num_labels = label_n

        # Using pyds.get_string() to get display_text as string
        # print(pyds.get_string(py_nvosd_text_params.display_text))
        print(".", end="", flush=True)
        pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)
        try:
            l_frame = l_frame.next
        except StopIteration:
            break

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
    # Check input arguments
    if len(args) != 2:
        sys.stderr.write("usage: %s <media file or uri>\n" % args[0])
        sys.exit(1)

    config_nvinfer = "config_y4tiny.txt"
    nvtracker_enabled = False  # Using Norfair
    config_nvtracker = "config_nvtracker.txt"
    codec = CODEC_H265
    input_filename = args[1]
    udp_sink_port = 5400
    # Streaming address: rtsp://<jetson-ip>:<rtsp-port>/<rtsp-address>
    rtsp_streaming_port = 8554
    rtsp_streaming_address = "/maskcam"
    # Original: 1920x1080, bdti_resized: 1024x576, yolo-input: 1024x608
    output_width = 1024
    output_height = 576
    output_bitrate = 4000000  # Nice for h264@1024x576
    streaming_clock_rate = 90000

    print(f"Playing file {input_filename}")
    print(f"Output codec: {codec}")

    # Standard GStreamer initialization
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

    source_bin = create_source_bin(0, input_filename)
    # Create nvstreammux instance to form batches from one or more sources.
    streammux = make_elm_or_print_err("nvstreammux", "Stream-muxer", "NvStreamMux")
    pgie = make_elm_or_print_err("nvinfer", "primary-inference", "pgie")

    # Tracker by nvidia (not used, kept just in case)
    if nvtracker_enabled:
        tracker = make_elm_or_print_err("nvtracker", "tracker", "Tracker")

    # Use convertor to convert from NV12 to RGBA as required by nvosd
    convert_pre_osd = make_elm_or_print_err(
        "nvvideoconvert", "convert_pre_osd", "Converter NV12->RGBA"
    )

    # Create OSD to draw on the converted RGBA buffer
    nvosd = make_elm_or_print_err("nvdsosd", "onscreendisplay", "OSD (nvosd)")

    # Finally encode and save the osd output
    queue = make_elm_or_print_err("queue", "queue", "Queue")
    convert_post_osd = make_elm_or_print_err(
        "nvvideoconvert", "convert_post_osd", "Converter RGBA->NV12"
    )

    # capsfilter: Optional check
    capsfilter = make_elm_or_print_err("capsfilter", "capsfilter", "capsfilter")

    # Recommended: H265 has more efficient compression
    if codec == CODEC_MP4:
        print("Creating MPEG-4 stream")
        encoder = make_elm_or_print_err(
            "avenc_mpeg4", "encoder", "Encoder", preload_reminder
        )
        codeparser = make_elm_or_print_err(
            "mpeg4videoparse", "mpeg4-parser", "Code Parser"
        )
        rtppay = make_elm_or_print_err("rtpmp4vpay", "rtppay", "RTP MPEG-44 Payload")
    elif codec == CODEC_H264:
        print("Creating H264 stream")
        encoder = make_elm_or_print_err(
            "nvv4l2h264enc", "encoder", "Encoder", preload_reminder
        )
        codeparser = make_elm_or_print_err("h264parse", "h264-parser", "Code Parser")
        rtppay = make_elm_or_print_err("rtph264pay", "rtppay", "RTP H264 Payload")
    else:  # Default: H265 (recommended)
        print("Creating H265 stream")
        encoder = make_elm_or_print_err(
            "nvv4l2h265enc", "encoder", "Encoder", preload_reminder
        )
        codeparser = make_elm_or_print_err("h265parse", "h265-parser", "Code Parser")
        rtppay = make_elm_or_print_err("rtph265pay", "rtppay", "RTP H265 Payload")

    # Split stream into file save and streaming: tee + queues
    splitter_file_udp = make_elm_or_print_err(
        "tee", "tee_file_udp", "Splitter file/UDP"
    )
    queue_udp = make_elm_or_print_err("queue", "queue_udp", "UDP queue")
    udpsink = make_elm_or_print_err("udpsink", "udpsink", "UDP Sink")

    streammux.set_property("width", output_width)
    streammux.set_property("height", output_height)
    streammux.set_property(
        "enable-padding", True
    )  # Keeps aspect ratio, but adds black margin

    streammux.set_property("batch-size", 1)
    streammux.set_property("batched-push-timeout", 4000000)

    # Inference element
    pgie.set_property("config-file-path", config_nvinfer)

    if nvtracker_enabled:
        set_nvtracker_configuration(tracker, config_nvtracker)

    # Nvidia OSD: Drawing element
    nvosd.set_property(
        "process-mode", 2
    )  # 0: CPU Mode, 1: GPU (only dGPU), 2: VIC (Jetson only)

    # nvosd.set_property("display-bbox", False)  # Bug: Removes all squares
    nvosd.set_property("display-clock", False)
    nvosd.set_property("display-text", True)  # Needed for any text

    # Caps check before encoding
    if codec == CODEC_MP4:  # Not hw accelerated
        caps = Gst.Caps.from_string("video/x-raw, format=I420")
    else:  # hw accelerated
        caps = Gst.Caps.from_string("video/x-raw(memory:NVMM), format=I420")
    capsfilter.set_property("caps", caps)

    encoder.set_property(
        "bitrate", output_bitrate
    )  # Nice quality w/h264@1024x576: 4000000
    # Taken from test1_rtsp_out python sample app
    # Works without this, and it's not documented, keep an eye on this
    encoder.set_property("preset-level", 1)
    encoder.set_property("insert-sps-pps", 1)
    encoder.set_property("bufapi-version", 1)

    # Make the UDP sink
    udpsink.set_property("host", "224.224.255.255")
    udpsink.set_property("port", udp_sink_port)
    udpsink.set_property("async", False)
    udpsink.set_property("sync", 1)

    print("Adding elements to Pipeline \n")
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
    pipeline.add(codeparser)
    pipeline.add(splitter_file_udp)
    pipeline.add(queue_udp)
    pipeline.add(rtppay)
    pipeline.add(udpsink)

    print("Linking elements in the Pipeline \n")

    # Pipeline Links
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
    encoder.link(splitter_file_udp)
    # Split stream to file and rtsp
    tee_rtsp = splitter_file_udp.get_request_pad("src_%u")

    # RTSP streaming
    tee_rtsp.link(queue_udp.get_static_pad("sink"))
    queue_udp.link(rtppay)
    rtppay.link(udpsink)

    # File split is done on request

    # Start streaming
    server = GstRtspServer.RTSPServer.new()
    server.props.service = str(rtsp_streaming_port)
    server.attach(None)

    factory = GstRtspServer.RTSPMediaFactory.new()
    factory.set_launch(
        f"( udpsrc name=pay0 port={udp_sink_port} buffer-size=524288"
        f' caps="application/x-rtp, media=video, clock-rate={streaming_clock_rate},'
        f' encoding-name=(string){codec}, payload=96 " )'
    )
    factory.set_shared(True)
    server.get_mount_points().add_factory(rtsp_streaming_address, factory)

    print(
        f"\n\nStreaming at rtsp://<jetson-ip>:{rtsp_streaming_port}{rtsp_streaming_address}\n\n"
    )

    # Lets add probe to get informed of the meta data generated, we add probe to
    # the sink pad of the osd element, since by that time, the buffer would have
    # had got all the metadata.
    osdsinkpad = nvosd.get_static_pad("sink")
    if not osdsinkpad:
        sys.stderr.write(" Unable to get sink pad of nvosd \n")

    osdsinkpad.add_probe(Gst.PadProbeType.BUFFER, osd_sink_pad_buffer_probe, 0)

    # start play back and listen to events
    print("Starting pipeline \n")
    pipeline.set_state(Gst.State.PLAYING)

    # create an event loop and feed gstreamer bus mesages to it
    bus = pipeline.get_bus()
    running = True
    file_save_status = 0

    while running:
        message = bus.pop()
        if message is not None:
            t = message.type
            if t == Gst.MessageType.EOS:
                sys.stdout.write("End-of-stream\n")
                running = False
            elif t == Gst.MessageType.WARNING:
                err, debug = message.parse_warning()
                sys.stderr.write("Warning: %s: %s\n" % (err, debug))
            elif t == Gst.MessageType.ERROR:
                err, debug = message.parse_error()
                sys.stderr.write("Error: %s: %s\n" % (err, debug))
                running = False
        else:
            time.sleep(10e-3)  # 10 millisecs

        if frame_number >= 100 and file_save_status == 0:

            queue_file = make_elm_or_print_err("queue", "queue_file", "File save queue")
            container = make_elm_or_print_err("qtmux", "qtmux", "Container")
            filesink = make_elm_or_print_err("filesink", "filesink", "File Sink")

            # File save
            output_filename = f"{input_filename.split('/')[-1].split('.')[0]}_out_1.mp4"
            filesink.set_property("location", output_filename)
            filesink.set_property("sync", 0)
            filesink.set_property("async", 0)

            pipeline.add(queue_file)
            pipeline.add(container)
            pipeline.add(filesink)

            if not queue_file.sync_state_with_parent():
                print("Could not add queue file element")
            if not container.sync_state_with_parent():
                print("Could not add file container element")
            if not filesink.sync_state_with_parent():
                print("Could not add filesink element")

            print(f"Saving file {output_filename}")
            tee_file = splitter_file_udp.get_request_pad("src_%u")
            tee_file.link(queue_file.get_static_pad("sink"))
            queue_file.link(codeparser)
            codeparser.link(container)
            container.link(filesink)
            file_save_status = 1
        elif frame_number >= 250:
            print("Finished saving files")
            running = False
            # Disconnect both

    # cleanup
    pipeline.set_state(Gst.State.NULL)


if __name__ == "__main__":
    sys.exit(main(sys.argv))

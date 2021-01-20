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
import time
import signal
import platform
import configparser
import threading
import multiprocessing as mp
from datetime import datetime
from rich import print

gi.require_version("Gst", "1.0")
gi.require_version("GstBase", "1.0")
gi.require_version("GstRtspServer", "1.0")
from gi.repository import GLib, Gst, GstRtspServer, GstBase
from common import CODEC_MP4, CODEC_H264, CODEC_H265, CONFIG_FILE

e_interrupt = None


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


def sigint_handler(sig, frame):
    # This function is not used if e_external_interrupt is provided
    print("\n[red]Ctrl+C pressed. Interrupting...[/red]")
    e_interrupt.set()


def main(
    config: dict,
    output_filename: str,
    e_external_interrupt: mp.Event = None,
):
    global e_interrupt

    udp_port = int(config["maskcam"]["udp-port"])
    codec = config["maskcam"]["codec"]
    streaming_clock_rate = int(config["maskcam"]["streaming-clock-rate"])

    udp_capabilities = f"application/x-rtp,media=video,encoding-name=(string){codec},clock-rate={streaming_clock_rate}"

    print(f"Codec: {codec}")

    # Standard GStreamer initialization
    # GObject.threads_init()  # Doesn't seem necessary (see https://pygobject.readthedocs.io/en/latest/guide/threading.html)
    Gst.init(None)

    # Create gstreamer elements
    # Create Pipeline element that will form a connection of other elements
    print("Creating Pipeline \n ")
    pipeline = Gst.Pipeline()

    if not pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")

    udpsrc = make_elm_or_print_err("udpsrc", "udpsrc", "UDP Source")
    udpsrc.set_property("port", udp_port)
    udpsrc.set_property("buffer-size", 524288)
    udpsrc.set_property("caps", Gst.Caps.from_string(udp_capabilities))
    rtpjitterbuffer = make_elm_or_print_err(
        "rtpjitterbuffer", "rtpjitterbuffer", "RTP Jitter Buffer"
    )
    # Default mode is 1 (slave), acts as a live source and gets laggy
    rtpjitterbuffer.set_property("mode", 4)

    # caps_udp = make_elm_or_print_err("capsfilter", "caps_udp", "UDP RTP capabilities")
    # caps_udp.set_property("caps", Gst.Caps.from_string(udp_capabilities))

    if codec == CODEC_MP4:
        print("Creating MPEG-4 payload decoder")
        rtpdepay = make_elm_or_print_err(
            "rtpmp4vpay", "rtpdepay", "RTP MPEG-4 Payload Decoder"
        )
        codeparser = make_elm_or_print_err(
            "mpeg4videoparse", "mpeg4-parser", "Code Parser"
        )
    elif codec == CODEC_H264:
        print("Creating H264 payload decoder")
        rtpdepay = make_elm_or_print_err(
            "rtph264depay", "rtpdepay", "RTP H264 Payload Decoder"
        )
        codeparser = make_elm_or_print_err("h264parse", "h264-parser", "Code Parser")
    else:  # Default: H265 (recommended)
        print("Creating H265 payload decoder")
        rtpdepay = make_elm_or_print_err(
            "rtph265depay", "rtpdepay", "RTP H265 Payload Decoder"
        )
        codeparser = make_elm_or_print_err("h265parse", "h265-parser", "Code Parser")

    # Workaround for this issue: https://gitlab.freedesktop.org/gstreamer/gst-plugins-good/-/issues/410
    GstBase.BaseParse.set_pts_interpolation(codeparser, True)

    container = make_elm_or_print_err("qtmux", "qtmux", "Container")
    filesink = make_elm_or_print_err("filesink", "filesink", "File Sink")
    filesink.set_property("location", output_filename)
    # filesink.set_property("sync", False)
    # filesink.set_property("async", False)

    pipeline.add(udpsrc)
    pipeline.add(rtpjitterbuffer)
    # pipeline.add(caps_udp)
    pipeline.add(rtpdepay)
    pipeline.add(codeparser)
    pipeline.add(container)
    pipeline.add(filesink)

    print("Linking elements in the Pipeline \n")

    # Pipeline Links
    udpsrc.link(rtpjitterbuffer)
    rtpjitterbuffer.link(rtpdepay)
    # caps_udp.link(rtpdepay)
    rtpdepay.link(codeparser)
    codeparser.link(container)
    container.link(filesink)

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
        print("[green bold]Press Ctrl+C to save video and exit[/green bold]")
    else:
        # If there's an external interrupt, don't capture SIGINT
        e_interrupt = e_external_interrupt

    # Custom event loop, allows saving file on Ctrl+C press
    running = True

    # start play back and listen to events
    print("Starting pipeline")
    pipeline.set_state(Gst.State.PLAYING)

    while running:
        g_context.iteration(may_block=False)
        message = bus.pop()
        if message is not None:
            t = message.type

            if t == Gst.MessageType.EOS:
                print(f"File saved: [yellow]{output_filename}[/yellow]")
                running = False
            elif t == Gst.MessageType.WARNING:
                err, debug = message.parse_warning()
                sys.stderr.write("Warning: %s: %s\n" % (err, debug))
            elif t == Gst.MessageType.ERROR:
                err, debug = message.parse_error()
                sys.stderr.write("Error: %s: %s\n" % (err, debug))
                running = False
        else:
            time.sleep(100e-3)  # Doesn't wait on messages
        if e_interrupt.is_set():
            print("Interruption received. Sending EOS to generate video file.")
            # This will allow the filesink to create a readable mp4 file
            container.send_event(Gst.Event.new_eos())
            e_interrupt.clear()

    print("File-saver main loop ending.")
    # cleanup
    pipeline.set_state(Gst.State.NULL)


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    config.sections()

    # Check arguments
    if len(sys.argv) > 1:
        output_filename = sys.argv[1]
    else:
        output_dir = config["maskcam"]["default-output-dir"]
        output_filename = (
            f"{output_dir}/{datetime.today().strftime('%Y%m%d_%H%M%S')}.mp4"
        )
    print(f"Output file: {output_filename}")

    sys.exit(main(config=config, output_filename=output_filename))

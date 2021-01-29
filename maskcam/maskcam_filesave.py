import os
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

gi.require_version("Gst", "1.0")
gi.require_version("GstBase", "1.0")
gi.require_version("GstRtspServer", "1.0")
from gi.repository import GLib, Gst, GstRtspServer, GstBase

from .prints import print_filesave as print
from .common import CODEC_MP4, CODEC_H264, CODEC_H265, CONFIG_FILE
from .utils import glib_cb_restart

e_interrupt = None


def make_elm_or_print_err(factoryname, name, printedname, detail=""):
    """Creates an element with Gst Element Factory make.
    Return the element  if successfully created, otherwise print
    to stderr and return None.
    """
    print("Creating", printedname)
    elm = Gst.ElementFactory.make(factoryname, name)
    if not elm:
        print("Unable to create " + printedname, error=True)
        if detail:
            print(detail)
    return elm


def sigint_handler(sig, frame):
    # This function is not used if e_external_interrupt is provided
    print("[red]Ctrl+C pressed. Interrupting file-save...[/red]")
    e_interrupt.set()


def main(
    config: dict,
    output_filename: str,
    e_external_interrupt: mp.Event = None,
):
    global e_interrupt

    udp_port = int(config["maskcam"]["udp-port-filesave"])
    codec = config["maskcam"]["codec"]
    streaming_clock_rate = int(config["maskcam"]["streaming-clock-rate"])

    udp_capabilities = f"application/x-rtp,media=video,encoding-name=(string){codec},clock-rate={streaming_clock_rate}"

    # Standard GStreamer initialization
    # GObject.threads_init()  # Doesn't seem necessary (see https://pygobject.readthedocs.io/en/latest/guide/threading.html)
    Gst.init(None)

    # Create gstreamer elements
    # Create Pipeline element that will form a connection of other elements
    print("[green]Creating:[/green] file-saving pipeline UDP->File")
    pipeline = Gst.Pipeline()

    if not pipeline:
        print("Unable to create Pipeline", error=True)

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

    # Periodic gloop interrupt (see utils.glib_cb_restart)
    t_check = 50
    GLib.timeout_add(t_check, glib_cb_restart, t_check)

    # Custom event loop, allows saving file on Ctrl+C press
    running = True

    # start play back and listen to events
    pipeline.set_state(Gst.State.PLAYING)
    print("[green]Playing:[/green] file-saving pipeline UDP->File\n")

    while running:
        g_context.iteration(may_block=True)
        message = bus.pop()
        if message is not None:
            t = message.type

            if t == Gst.MessageType.EOS:
                print(f"File saved: [yellow]{output_filename}[/yellow]")
                running = False
            elif t == Gst.MessageType.WARNING:
                err, debug = message.parse_warning()
                print("%s: %s" % (err, debug), warning=True)
            elif t == Gst.MessageType.ERROR:
                err, debug = message.parse_error()
                print("%s: %s" % (err, debug), error=True)
                running = False
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
        output_dir = config["maskcam"]["fileserver-hdd-dir"]
        output_filename = (
            f"{output_dir}/{datetime.today().strftime('%Y%m%d_%H%M%S')}.mp4"
        )
    print(f"Output file: {output_filename}")

    sys.exit(main(config=config, output_filename=output_filename))

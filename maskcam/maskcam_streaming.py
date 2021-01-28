import gi
import pyds
import sys
import time
import signal
import platform
import threading
import configparser
import multiprocessing as mp
from datetime import datetime

gi.require_version("Gst", "1.0")
gi.require_version("GstRtspServer", "1.0")
from gi.repository import GLib, Gst, GstRtspServer

from .prints import print_streaming as print
from .utils import get_ip_address, glib_cb_restart
from .common import CODEC_MP4, CODEC_H264, CODEC_H265, CONFIG_FILE

e_interrupt = None


def sigint_handler(sig, frame):
    # This function is not used if e_external_interrupt is provided
    print("[red]Ctrl+C pressed. Interrupting streaming...[/red]")
    e_interrupt.set()


def main(config, e_external_interrupt: mp.Event = None):
    global e_interrupt
    udp_port = int(config["maskcam"]["udp-port"])
    codec = config["maskcam"]["codec"]
    # Streaming address: rtsp://<jetson-ip>:<rtsp-port>/<rtsp-address>
    rtsp_streaming_port = int(config["maskcam"]["streaming-port"])
    rtsp_streaming_address = "/maskcam"
    streaming_clock_rate = int(config["maskcam"]["streaming-clock-rate"])

    # udp_capabilities = f"application/x-rtp,media=video,encoding-name={codec},payload=96"

    print(f"Codec: {codec}")

    # Standard GStreamer initialization
    Gst.init(None)

    # Start streaming
    server = GstRtspServer.RTSPServer.new()
    server.props.service = str(rtsp_streaming_port)
    server.attach(None)

    factory = GstRtspServer.RTSPMediaFactory.new()
    factory.set_launch(
        f"( udpsrc name=pay0 port={udp_port} buffer-size=524288"
        f' caps="application/x-rtp, media=video, clock-rate={streaming_clock_rate},'
        f' encoding-name=(string){codec}, payload=96 " )'
    )
    factory.set_shared(True)
    server.get_mount_points().add_factory(rtsp_streaming_address, factory)

    print(
        f"\n\n[green bold]Streaming[/green bold] at rtsp://{get_ip_address()}:{rtsp_streaming_port}{rtsp_streaming_address}\n\n"
    )

    # GLib loop required for RTSP server
    g_loop = GLib.MainLoop()
    g_context = g_loop.get_context()

    if e_external_interrupt is None:
        # Use threading instead of mp.Event() for sigint_handler, see:
        # https://bugs.python.org/issue41606
        e_interrupt = threading.Event()
        signal.signal(signal.SIGINT, sigint_handler)
        print("[green bold]Press Ctrl+C to stop pipeline[/green bold]")
    else:
        # If there's an external interrupt, don't capture SIGINT
        e_interrupt = e_external_interrupt

    # Periodic gloop interrupt (see utils.glib_cb_restart)
    t_check = 100
    GLib.timeout_add(t_check, glib_cb_restart, t_check)

    while not e_interrupt.is_set():
        g_context.iteration(may_block=True)

    print("Ending streaming")


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    config.sections()
    main(config)

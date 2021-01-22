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
from datetime import datetime
from rich import print

gi.require_version("Gst", "1.0")
gi.require_version("GstRtspServer", "1.0")
from gi.repository import GLib, Gst, GstRtspServer
from utils import get_ip_address
from common import CODEC_MP4, CODEC_H264, CODEC_H265, CONFIG_FILE


def main(args):
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    config.sections()
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

    try:
        g_loop.run()
    except KeyboardInterrupt:
        print("\n[yellow]Keyboard interruption received[/yellow]")
    except Exception as e:
        print(f"Exception: {e}")
    print("Ending streaming")


if __name__ == "__main__":
    sys.exit(main(sys.argv))

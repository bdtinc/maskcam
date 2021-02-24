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

from .config import config
from gi.repository import GLib

ADDRESS_UNKNOWN_LABEL = "<device-address-not-configured>"


def get_ip_address():
    result_value = config["maskcam"]["device-address"].strip()
    if not result_value or result_value == "0":
        result_value = ADDRESS_UNKNOWN_LABEL
    return result_value


def get_streaming_address(host_address, rtsp_port, rtsp_path):
    return f"rtsp://{host_address}:{rtsp_port}{rtsp_path}"


def format_tdelta(time_delta):
    # Format to show timedelta objects as string
    if time_delta is None:
        return "N/A"
    return f"{time_delta}".split(".")[0]  # Remove nanoseconds


def glib_cb_restart(t_restart):
    # Timer to avoid GLoop locking infinitely
    # We want to run g_context.iteration(may_block=True)
    # since may_block=False will use high CPU,
    # and adding sleeps lags event processing.
    # But we want to check periodically for other events
    GLib.timeout_add(t_restart, glib_cb_restart, t_restart)


def load_udp_ports_filesaving(config, udp_ports_pool):
    for port in config["maskcam"]["udp-ports-filesave"].split(","):
        udp_ports_pool.add(int(port))
    return udp_ports_pool

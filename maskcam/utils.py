import socket
from gi.repository import GLib

_cached_values = {}


def get_ip_address():
    if "ip_address" not in _cached_values:
        # This trick doesn't need internet connection
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("1.1.1.1", 80))
            _cached_values["ip_address"] = f"{s.getsockname()[0]}"
    return _cached_values["ip_address"]


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

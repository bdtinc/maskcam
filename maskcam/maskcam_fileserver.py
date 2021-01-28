import os
import sys
import time
import socket
import configparser
import threading
import multiprocessing as mp
from datetime import datetime
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer, ThreadingTCPServer

from .common import CONFIG_FILE
from .utils import get_ip_address
from .prints import print_fileserver as print


class Handler(SimpleHTTPRequestHandler):
    # Needed to set extensions_map
    pass


def start_server(httpd_server):
    httpd_server.serve_forever(poll_interval=0.5)


def cb_handle_error(request, client_address):
    # Not important, happens very often but nothing actually fails
    print(f"Static file server: File request interrupted [client: {client_address}]")


def main(config, directory=None, e_external_interrupt: mp.Event = None):
    if directory is None:
        directory = config["maskcam"]["fileserver-hdd-dir"]
    directory = os.fspath(directory)
    print(f"Serving static files from directory: [yellow]{directory}[/yellow]")

    port = int(config["maskcam"]["fileserver-port"])

    # Create dir if doesn't exist
    os.system(f"mkdir -p {directory}")
    os.chdir(directory)  # easiest way

    # Force download mp4 files
    Handler.extensions_map[".mp4"] = "application/octet-stream"

    print(f"[green]Static server STARTED[/green] at http://{get_ip_address()}:{port}")
    with ThreadingTCPServer(("", port), Handler) as httpd:
        httpd.handle_error = cb_handle_error
        s = threading.Thread(target=start_server, args=(httpd,))
        s.start()
        try:
            if e_external_interrupt is not None:
                e_external_interrupt.wait()  # blocking
            else:
                s.join()  # blocking
        except KeyboardInterrupt:
            print("Ctrl+C pressed")
        print("Shutting down static file server")
        httpd.shutdown()
        httpd.server_close()
        s.join(timeout=1)
        if s.is_alive():
            print("Server thread did not stop", warning=True)
        else:
            print("Server shut down correctly")
    print(f"Server alive threads: {threading.enumerate()}")


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    config.sections()

    # Input source
    directory = sys.argv[1] if len(sys.argv) > 1 else None
    main(config, directory=directory)
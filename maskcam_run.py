#!/usr/bin/env python3

################################################################################
# Copyright (c) 2020-2021, Berkeley Design Technology Inc. All rights reserved.
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
import sys
import json
import shutil
import signal
import threading
import multiprocessing as mp

# Avoids random hangs in child processes (https://pythonspeed.com/articles/python-multiprocessing/)
mp.set_start_method("spawn")  # noqa

from rich.console import Console
from datetime import datetime, timedelta

from maskcam.prints import print_run as print
from maskcam.config import config, print_config_overrides
from maskcam.common import USBCAM_PROTOCOL, RASPICAM_PROTOCOL
from maskcam.common import (
    CMD_FILE_SAVE,
    CMD_STREAMING_START,
    CMD_STREAMING_STOP,
    CMD_INFERENCE_RESTART,
    CMD_FILESERVER_RESTART,
    CMD_STATUS_REQUEST,
)
from maskcam.utils import (
    get_ip_address,
    ADDRESS_UNKNOWN_LABEL,
    load_udp_ports_filesaving,
    get_streaming_address,
    format_tdelta,
)
from maskcam.mqtt_common import mqtt_connect_broker, mqtt_send_msg
from maskcam.mqtt_common import (
    MQTT_BROKER_IP,
    MQTT_BROKER_PORT,
    MQTT_DEVICE_DESCRIPTION,
    MQTT_DEVICE_NAME,
)
from maskcam.mqtt_common import (
    MQTT_TOPIC_ALERTS,
    MQTT_TOPIC_FILES,
    MQTT_TOPIC_HELLO,
    MQTT_TOPIC_STATS,
    MQTT_TOPIC_UPDATE,
    MQTT_TOPIC_COMMANDS,
)
from maskcam.maskcam_inference import main as inference_main
from maskcam.maskcam_filesave import main as filesave_main
from maskcam.maskcam_fileserver import main as fileserver_main
from maskcam.maskcam_streaming import main as streaming_main


udp_ports_pool = set()
console = Console()
# Use threading.Event instead of mp.Event() for sigint_handler, see:
# https://bugs.python.org/issue41606
e_interrupt = threading.Event()
q_commands = mp.Queue(maxsize=4)
active_filesave_processes = []

P_INFERENCE = "inference"
P_STREAMING = "streaming"
P_FILESERVER = "file-server"
P_FILESAVE_PREFIX = "file-save-"

processes_info = {}


def sigint_handler(sig, frame):
    print("[red]Ctrl+C pressed. Interrupting all processes...[/red]")
    e_interrupt.set()


def start_process(name, target_function, config, **kwargs):
    e_interrupt_process = mp.Event()
    process = mp.Process(
        name=name,
        target=target_function,
        kwargs=dict(
            e_external_interrupt=e_interrupt_process,
            config=config,
            **kwargs,
        ),
    )
    processes_info[name] = {"started": datetime.now(), "running": True}
    process.start()
    print(f"Process [yellow]{name}[/yellow] started with PID: {process.pid}")
    return process, e_interrupt_process


def terminate_process(name, process, e_interrupt_process, delete_info=False):
    print(f"Sending interrupt to {name} process")
    e_interrupt_process.set()
    print(f"Waiting for process [yellow]{name}[/yellow] to terminate...")
    process.join(timeout=10)
    if process.is_alive():
        print(
            f"[red]Forcing termination of process:[/red] [bold]{name}[/bold]",
            warning=True,
        )
        process.terminate()
    if name in processes_info:
        if delete_info:
            del processes_info[name]  # Sequential processes, avoid filling memory
        else:
            processes_info[name].update({"ended": datetime.now(), "running": False})
    print(f"Process terminated: [yellow]{name}[/yellow]\n")


def new_command(command):
    if q_commands.full():
        print(f"Command {command} IGNORED. Queue is full.", error=True)
        return
    print(f"Received command: [yellow]{command}[/yellow]")
    q_commands.put_nowait(command)


def mqtt_init(config):
    if MQTT_BROKER_IP is None or MQTT_DEVICE_NAME is None:
        print(
            "[red]MQTT is DISABLED[/red]"
            " since MQTT_BROKER_IP or MQTT_DEVICE_NAME env vars are not defined\n",
            warning=True,
        )
        mqtt_client = None
    else:
        print(f"Connecting to MQTT server {MQTT_BROKER_IP}:{MQTT_BROKER_PORT}")
        print(f"Device name: [green]{MQTT_DEVICE_NAME}[/green]\n\n")
        mqtt_client = mqtt_connect_broker(
            client_id=MQTT_DEVICE_NAME,
            broker_ip=MQTT_BROKER_IP,
            broker_port=MQTT_BROKER_PORT,
            subscribe_to=[(MQTT_TOPIC_COMMANDS, 2)],  # handles re-subscription
            cb_success=mqtt_on_connect,
        )
        mqtt_client.on_message = mqtt_process_message

        return mqtt_client


def mqtt_on_connect(mqtt_client):
    mqtt_say_hello(mqtt_client)
    mqtt_send_file_list(mqtt_client)


def mqtt_process_message(mqtt_client, userdata, message):
    topic = message.topic
    if topic == MQTT_TOPIC_COMMANDS:
        payload = json.loads(message.payload.decode())

        if payload["device_id"] != MQTT_DEVICE_NAME:
            return
        command = payload["command"]
        new_command(command)


def mqtt_say_hello(mqtt_client):
    return mqtt_send_msg(
        mqtt_client,
        MQTT_TOPIC_HELLO,
        {"device_id": MQTT_DEVICE_NAME, "description": MQTT_DEVICE_DESCRIPTION},
        enqueue=False,  # Will be resent on_connect
    )


def mqtt_send_device_status(mqtt_client):
    t_now = datetime.now()
    device_address = get_ip_address()
    is_valid_address = device_address != ADDRESS_UNKNOWN_LABEL
    if P_INFERENCE in processes_info and processes_info[P_INFERENCE]["running"]:
        inference_runtime = t_now - processes_info[P_INFERENCE]["started"]
    else:
        inference_runtime = None
    if P_FILESERVER in processes_info and processes_info[P_FILESERVER]["running"]:
        fileserver_runtime = t_now - processes_info[P_FILESERVER]["started"]
    else:
        fileserver_runtime = None
    if P_STREAMING in processes_info and processes_info[P_STREAMING]["running"]:
        streaming_address = get_streaming_address(
            device_address,
            config["maskcam"]["streaming-port"],
            config["maskcam"]["streaming-path"],
        )
    else:
        streaming_address = "N/A"
    total_fsave = len(active_filesave_processes)
    keep_n = len([p for p in active_filesave_processes if p["flag_keep_file"]])
    return mqtt_send_msg(
        mqtt_client,
        MQTT_TOPIC_UPDATE,
        {
            "device_id": MQTT_DEVICE_NAME,
            "inference_runtime": format_tdelta(inference_runtime),
            "fileserver_runtime": format_tdelta(fileserver_runtime),
            "streaming_address": streaming_address,
            "device_address": device_address if is_valid_address else None,
            "save_current_files": f"{keep_n}/{total_fsave}",
            "time": f"{t_now:%H:%M:%S}",
        },
        enqueue=False,  # Only latest status is interesting
    )


def mqtt_send_file_list(mqtt_client):
    server_address = get_ip_address()
    server_port = int(config["maskcam"]["fileserver-port"])
    try:
        file_list = sorted(os.listdir(config["maskcam"]["fileserver-hdd-dir"]))
    except FileNotFoundError:  # directory not created
        file_list = []
    return mqtt_send_msg(
        mqtt_client,
        MQTT_TOPIC_FILES,
        {
            "device_id": MQTT_DEVICE_NAME,
            "file_server": f"http://{server_address}:{server_port}",
            "file_list": file_list,
        },
        enqueue=False,  # Will be resent on_connect or when something changes
    )


def is_alert_condition(statistics, config):
    # Thresholds config
    max_total_people = int(config["maskcam"]["alert-max-total-people"])
    min_visible_people = int(config["maskcam"]["alert-min-visible-people"])
    max_no_mask = float(config["maskcam"]["alert-no-mask-fraction"])

    # Calculate visible people
    without_mask = int(statistics["people_without_mask"])
    with_mask = int(statistics["people_with_mask"])
    visible_people = with_mask + without_mask
    is_alert = False
    if statistics["people_total"] > max_total_people:
        is_alert = True
    elif visible_people >= min_visible_people:
        no_mask_fraction = float(statistics["people_without_mask"]) / visible_people
        is_alert = no_mask_fraction > max_no_mask

    print(f"[yellow]ALERT condition: {is_alert}[/yellow]")
    return is_alert


def handle_statistics(mqtt_client, stats_queue, config, is_live_input):
    while not stats_queue.empty():
        statistics = stats_queue.get_nowait()

        if is_live_input:
            # Alert conditions detection
            raise_alert = is_alert_condition(statistics, config)
            if raise_alert:
                flag_keep_current_files()

            if mqtt_client is not None:
                topic = MQTT_TOPIC_ALERTS if raise_alert else MQTT_TOPIC_STATS
                message = {"device_id": MQTT_DEVICE_NAME, **statistics}
                mqtt_send_msg(mqtt_client, topic, message, enqueue=True)


def allocate_free_udp_port():
    new_port = udp_ports_pool.pop()
    print(f"Allocating UDP port: {new_port}")
    return new_port


def release_udp_port(port_number):
    print(f"Releasing UDP port: {port_number}")
    udp_ports_pool.add(port_number)


def handle_file_saving(
    video_period, video_duration, ram_dir, hdd_dir, force_save, mqtt_client=None
):
    period = timedelta(seconds=video_period)
    duration = timedelta(seconds=video_duration)
    latest_start = None
    latest_number = 0

    # Handle termination of previous file-saving processes and move files RAM->HDD
    terminated_idxs = []
    for idx, active_process in enumerate(active_filesave_processes):
        if datetime.now() - active_process["started"] >= duration:
            finish_filesave_process(active_process, hdd_dir, force_save, mqtt_client=mqtt_client)
            terminated_idxs.append(idx)
        if latest_start is None or active_process["started"] > latest_start:
            latest_start = active_process["started"]
            latest_number = active_process["number"]

    # Remove terminated processes from list in a separated loop
    for idx in sorted(terminated_idxs, reverse=True):
        del active_filesave_processes[idx]

    # Start new file-saving process if time has elapsed
    if latest_start is None or (datetime.now() - latest_start >= period):
        print(
            "[green]Time to start a new video file [/green]"
            f" (latest started at: {format_tdelta(latest_start)})"
        )
        new_process_number = latest_number + 1
        new_process_name = f"{P_FILESAVE_PREFIX}{new_process_number}"
        new_filename = f"{datetime.today().strftime('%Y%m%d_%H%M%S')}_{new_process_number}.mp4"
        new_filepath = f"{ram_dir}/{new_filename}"
        new_udp_port = allocate_free_udp_port()
        process_handler, e_interrupt_process = start_process(
            new_process_name,
            filesave_main,
            config,
            output_filename=new_filepath,
            udp_port=new_udp_port,
        )
        active_filesave_processes.append(
            dict(
                number=new_process_number,
                name=new_process_name,
                filepath=new_filepath,
                filename=new_filename,
                started=datetime.now(),
                process_handler=process_handler,
                e_interrupt=e_interrupt_process,
                flag_keep_file=False,
                udp_port=new_udp_port,
            )
        )


def finish_filesave_process(active_process, hdd_dir, force_filesave, mqtt_client=None):
    terminate_process(
        active_process["name"],
        active_process["process_handler"],
        active_process["e_interrupt"],
        delete_info=True,
    )
    release_udp_port(active_process["udp_port"])

    # Move file to its definitive place if flagged, otherwise remove it
    if active_process["flag_keep_file"] or force_filesave:
        definitive_filepath = f"{hdd_dir}/{active_process['filename']}"
        print(f"Force file saving: {bool(force_filesave)}")
        print(f"Permanent video file created: [green]{definitive_filepath}[/green]")
        # Must use shutil here to move RAM->HDD
        shutil.move(active_process["filepath"], definitive_filepath)
        # Send updated file list via MQTT (prints ignore if mqtt_client is None)
        mqtt_send_file_list(mqtt_client)
    else:
        print(f"Removing RAM video file: {active_process['filepath']}")
        os.remove(active_process["filepath"])


def flag_keep_current_files():
    print("Request to [green]save current video files[/green]")
    for process in active_filesave_processes:
        print(f"Set flag to keep: [green]{process['filename']}[/green]")
        process["flag_keep_file"] = True


if __name__ == "__main__":
    if len(sys.argv) > 2:
        print(
            """Usage: python3 maskcam_run.py [ URI ]
        Examples:
        \t$ python3 maskcam_run.py
        \t$ python3 maskcam_run.py file:///absolute/path/to/file.mp4
        \t$ python3 maskcam_run.py v4l2:///dev/video1
        \t$ python3 maskcam_run.py argus://0

        Notes:
        \t - If no URI is provided, will use default-input defined in config_maskcam.txt
        \t - If a file:///path/file.mp4 is provided, the output will be ./output_file.mp4
        \t - If the input is a live camera, the output will be consecutive
        \t   video files under /dev/shm/date_time.mp4
        \t   according to the time interval defined in output-chunks-duration in config_maskcam.txt.
        """
        )
        sys.exit(0)
    try:
        # Print any ENV var config override to avoid confusions
        print_config_overrides()

        # Input source
        if len(sys.argv) > 1:
            input_filename = sys.argv[1]
            print(f"Provided input source: {input_filename}")
        else:
            input_filename = config["maskcam"]["default-input"]
            print(f"Using input from config file: {input_filename}")

        # Input type: file or live camera
        is_usbcamera = USBCAM_PROTOCOL in input_filename
        is_raspicamera = RASPICAM_PROTOCOL in input_filename
        is_live_input = is_usbcamera or is_raspicamera

        # Streaming enabled by default?
        streaming_autostart = int(config["maskcam"]["streaming-start-default"])

        # Fileserver: sequentially save videos (only for camera input)
        fileserver_enabled = is_live_input and int(config["maskcam"]["fileserver-enabled"])
        fileserver_period = int(config["maskcam"]["fileserver-video-period"])
        fileserver_duration = int(config["maskcam"]["fileserver-video-duration"])
        fileserver_force_save = int(config["maskcam"]["fileserver-force-save"])
        fileserver_ram_dir = config["maskcam"]["fileserver-ram-dir"]
        fileserver_hdd_dir = config["maskcam"]["fileserver-hdd-dir"]

        # Inference restart timeout
        tout_inference_restart = int(config["maskcam"]["timeout-inference-restart"])
        if is_live_input and tout_inference_restart:
            tout_inference_restart = timedelta(seconds=tout_inference_restart)
        else:
            tout_inference_restart = 0

        # Filesave processes: load available ports
        load_udp_ports_filesaving(config, udp_ports_pool)

        # Should only have 1 element at a time unless this thread gets blocked
        stats_queue = mp.Queue(maxsize=5)

        # Init MQTT or set these to None
        if is_live_input:
            mqtt_client = mqtt_init(config)
        else:
            mqtt_client = None

        # SIGINT handler (Ctrl+C)
        signal.signal(signal.SIGINT, sigint_handler)
        print("[green bold]Press Ctrl+C to stop all processes[/green bold]")

        process_inference = None
        process_streaming = None
        process_fileserver = None
        e_inference_ready = mp.Event()

        if fileserver_enabled:
            process_fileserver, e_interrupt_fileserver = start_process(
                P_FILESERVER, fileserver_main, config, directory=fileserver_hdd_dir
            )

        if streaming_autostart:
            print("[yellow]Starting streaming (streaming-start-default is set)[/yellow]")
            new_command(CMD_STREAMING_START)

        # Inference process: If input is a file, also saves file
        output_filename = None if is_live_input else f"output_{input_filename.split('/')[-1]}"
        process_inference, e_interrupt_inference = start_process(
            P_INFERENCE,
            inference_main,
            config,
            input_filename=input_filename,
            output_filename=output_filename,
            stats_queue=stats_queue,
            e_ready=e_inference_ready,
        )

        while not e_interrupt.is_set():
            # Send MQTT statistics, detect alarm events and request file-saving
            handle_statistics(mqtt_client, stats_queue, config, is_live_input)

            # Handle sequential file saving processes, only after inference process is ready
            if e_inference_ready.is_set():
                if fileserver_enabled and is_live_input:  # server can be enabled via MQTT
                    handle_file_saving(
                        fileserver_period,
                        fileserver_duration,
                        fileserver_ram_dir,
                        fileserver_hdd_dir,
                        fileserver_force_save,
                        mqtt_client=mqtt_client,
                    )

            if not q_commands.empty():
                command = q_commands.get_nowait()
                reply_updated_status = False
                print(f"Processing command: [yellow]{command}[yellow]")
                if command == CMD_STREAMING_START:
                    if process_streaming is None or not process_streaming.is_alive():
                        process_streaming, e_interrupt_streaming = start_process(
                            P_STREAMING, streaming_main, config
                        )
                    reply_updated_status = True
                elif command == CMD_STREAMING_STOP:
                    if process_streaming is not None and process_streaming.is_alive():
                        terminate_process(P_STREAMING, process_streaming, e_interrupt_streaming)
                    reply_updated_status = True
                elif command == CMD_INFERENCE_RESTART:
                    if process_inference.is_alive():
                        terminate_process(P_INFERENCE, process_inference, e_interrupt_inference)
                    process_inference, e_interrupt_inference = start_process(
                        P_INFERENCE,
                        inference_main,
                        config,
                        input_filename=input_filename,
                        output_filename=output_filename,
                        stats_queue=stats_queue,
                    )
                    reply_updated_status = True
                elif command == CMD_FILESERVER_RESTART:
                    if process_fileserver is not None and process_fileserver.is_alive():
                        terminate_process(P_FILESERVER, process_fileserver, e_interrupt_fileserver)
                    process_fileserver, e_interrupt_fileserver = start_process(
                        P_FILESERVER,
                        fileserver_main,
                        config,
                        directory=fileserver_hdd_dir,
                    )
                    fileserver_enabled = True
                    reply_updated_status = True
                elif command == CMD_FILE_SAVE:
                    flag_keep_current_files()
                    reply_updated_status = True
                elif command == CMD_STATUS_REQUEST:
                    reply_updated_status = True
                else:
                    print("[red]Command not recognized[/red]", error=True)

                if reply_updated_status:
                    mqtt_send_device_status(mqtt_client)
            else:
                e_interrupt.wait(timeout=0.1)

            # Routine check: finish loop if the inference process is dead
            if not process_inference.is_alive():
                e_interrupt.set()

            # Routine check: restart inference at given interval (only live_input)
            if tout_inference_restart:
                inference_runtime = datetime.now() - processes_info[P_INFERENCE]["started"]
                if inference_runtime > tout_inference_restart:
                    print(
                        "[yellow]Restarting inference due to timeout-inference-restart"
                        f"(inference runtime: {format_tdelta(inference_runtime)})[/yellow]"
                    )
                    new_command(CMD_INFERENCE_RESTART)

    except:  # noqa
        console.print_exception()

    # Terminate all running processes, avoid breaking on any exception
    for active_file_process in active_filesave_processes:
        try:
            finish_filesave_process(
                active_file_process,
                fileserver_hdd_dir,
                fileserver_force_save,
                mqtt_client=mqtt_client,
            )
        except:  # noqa
            console.print_exception()
    try:
        if process_inference is not None and process_inference.is_alive():
            terminate_process(P_INFERENCE, process_inference, e_interrupt_inference)
    except:  # noqa
        console.print_exception()
    try:
        if process_fileserver is not None and process_fileserver.is_alive():
            terminate_process(P_FILESERVER, process_fileserver, e_interrupt_fileserver)
    except:  # noqa
        console.print_exception()
    try:
        if process_streaming is not None and process_streaming.is_alive():
            terminate_process(P_STREAMING, process_streaming, e_interrupt_streaming)
    except:  # noqa
        console.print_exception()

import os
import sys
import time
import json
import shutil
import signal
import threading
import configparser
import multiprocessing as mp

from rich import print
from rich.console import Console
from datetime import datetime, timedelta

from common import CONFIG_FILE, USBCAM_PROTOCOL, RASPICAM_PROTOCOL
from common import (
    CMD_FILE_SAVE,
    CMD_STREAMING_START,
    CMD_STREAMING_STOP,
    CMD_INFERENCE_RESTART,
    CMD_FILESERVER_RESTART,
)
from utils import get_ip_address
from mqtt_common import mqtt_connect_broker, mqtt_send_msg
from mqtt_common import (
    MQTT_BROKER_IP,
    MQTT_BROKER_PORT,
    MQTT_DEVICE_DESCRIPTION,
    MQTT_DEVICE_NAME,
)
from mqtt_common import (
    MQTT_TOPIC_ALERTS,
    MQTT_TOPIC_FILES,
    MQTT_TOPIC_HELLO,
    MQTT_TOPIC_STATS,
    MQTT_TOPIC_COMMANDS,
)
from maskcam_inference import main as inference_main
from maskcam_filesave import main as filesave_main
from maskcam_fileserver import main as fileserver_main
from maskcam_streaming import main as streaming_main


# mp.set_start_method("spawn")

# Use threading instead of mp.Event() for sigint_handler, see:
# https://bugs.python.org/issue41606
e_interrupt = threading.Event()
q_commands = mp.Queue(maxsize=4)
active_filesave_processes = []
console = Console()

config = configparser.ConfigParser()
config.read(CONFIG_FILE)
config.sections()


def sigint_handler(sig, frame):
    print("\n[red]Ctrl+C pressed. Interrupting all processes...[/red]")
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
    process.start()
    print(f"Process [yellow]{name}[/yellow] started with PID: {process.pid}")
    return process, e_interrupt_process


def terminate_process(name, process, e_interrupt_process):
    print(f"\nSending interrupt to {name} process")
    e_interrupt_process.set()
    print(f"Waiting for process [yellow]{name}[/yellow] to terminate...")
    process.join(timeout=10)
    if process.is_alive():
        print(f"[red]Forcing termination of process:[/red] [bold]{name}[/bold]")
        process.terminate()
    print(f"Process terminated: [yellow]{name}[/yellow]\n")


def new_command(command):
    if q_commands.full():
        console.log(f"[red]Command {command} IGNORED[/red]. Queue is full.")
        return
    print(f"Received command: [yellow]{command}[/yellow]")
    q_commands.put_nowait(command)


def mqtt_init(config):
    if MQTT_BROKER_IP is None or MQTT_DEVICE_NAME is None:
        print(
            "\n[red]MQTT is DISABLED[/red]"
            " since MQTT_BROKER_IP or MQTT_DEVICE_NAME env vars are not defined\n"
        )
        mqtt_client = None
    else:
        print(f"\nConnecting to MQTT server {MQTT_BROKER_IP}:{MQTT_BROKER_PORT}")
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


def mqtt_send_file_list(mqtt_client):
    server_address = get_ip_address()
    server_port = int(config["maskcam"]["fileserver-port"])
    try:
        file_list = sorted(os.listdir(config["maskcam"]["fileserver-hdd-dir"]))
    except FileNotFoundError:
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


def handle_statistics(mqtt_client, stats_queue, config):
    while not stats_queue.empty():
        statistics = stats_queue.get_nowait()

        # Alert conditions detection
        raise_alert = is_alert_condition(statistics, config)
        if raise_alert:
            flag_keep_current_files()

        if mqtt_client is not None:
            topic = MQTT_TOPIC_ALERTS if raise_alert else MQTT_TOPIC_STATS
            message = {"device_id": MQTT_DEVICE_NAME, **statistics}
            mqtt_send_msg(mqtt_client, topic, message, enqueue=True)


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
            finish_filesave_process(
                active_process, hdd_dir, force_save, mqtt_client=mqtt_client
            )
            terminated_idxs.append(idx)
        if latest_start is None or active_process["started"] > latest_start:
            latest_start = active_process["started"]
            latest_number = active_process["number"]

    # Remove terminated processes from list in a separated loop
    for idx in sorted(terminated_idxs, reverse=True):
        del active_filesave_processes[idx]

    # Start new file-saving process if time has elapsed
    if latest_start is None or (datetime.now() - latest_start >= period):
        console.log(
            "[green]Time to start a new video file [/green]"
            f" [latest started at: {latest_start}]"
        )
        new_process_number = latest_number + 1
        new_process_name = f"file-save-{new_process_number}"
        new_filename = (
            f"{datetime.today().strftime('%Y%m%d_%H%M%S')}_{new_process_number}.mp4"
        )
        new_filepath = f"{ram_dir}/{new_filename}"
        process_handler, e_interrupt_process = start_process(
            new_process_name, filesave_main, config, output_filename=new_filepath
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
            )
        )


def finish_filesave_process(active_process, hdd_dir, force_filesave, mqtt_client=None):
    terminate_process(
        active_process["name"],
        active_process["process_handler"],
        active_process["e_interrupt"],
    )

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
        \t - If a file:///path/file.mp4 is provided, the output will be output_file.mp4 in the current dir
        \t - If the input is a live camera, the output will be consecutive
        \t   video files under /dev/shm/date_time.mp4
        \t   according to the time interval defined in output-chunks-duration in config_maskcam.txt.
        """
        )
        sys.exit(0)
    try:
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

        # Fileserver: sequentially save videos (only for camera input)
        fileserver_enabled = is_live_input and int(
            config["maskcam"]["fileserver-enabled"]
        )
        fileserver_period = int(config["maskcam"]["fileserver-video-period"])
        fileserver_duration = int(config["maskcam"]["fileserver-video-duration"])
        fileserver_force_save = int(config["maskcam"]["fileserver-force-save"])
        fileserver_ram_dir = config["maskcam"]["fileserver-ram-dir"]
        fileserver_hdd_dir = config["maskcam"]["fileserver-hdd-dir"]

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

        if fileserver_enabled:
            process_fileserver, e_interrupt_fileserver = start_process(
                "file-server", fileserver_main, config, directory=fileserver_hdd_dir
            )

        # Inference process: If input is a file, also saves file
        output_filename = (
            None if is_live_input else f"output_{input_filename.split('/')[-1]}"
        )
        process_inference, e_interrupt_inference = start_process(
            "inference",
            inference_main,
            config,
            input_filename=input_filename,
            output_filename=output_filename,
            stats_queue=stats_queue,
        )

        while not e_interrupt.is_set():
            # Send MQTT statistics, detect alarm events and request file-saving
            handle_statistics(mqtt_client, stats_queue, config)

            # Handle sequential file saving processes
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
                print(f"Processing command: [yellow]{command}[yellow]")
                if command == CMD_STREAMING_START:
                    if process_streaming is None or not process_streaming.is_alive():
                        process_streaming, e_interrupt_streaming = start_process(
                            "streaming", streaming_main, config
                        )
                elif command == CMD_STREAMING_STOP:
                    if process_streaming is not None and process_streaming.is_alive():
                        terminate_process(
                            "streaming", process_streaming, e_interrupt_streaming
                        )
                elif command == CMD_INFERENCE_RESTART:
                    if process_inference.is_alive():
                        terminate_process(
                            "inference", process_inference, e_interrupt_inference
                        )
                    process_inference, e_interrupt_inference = start_process(
                        "inference",
                        inference_main,
                        config,
                        input_filename=input_filename,
                        output_filename=output_filename,
                        stats_queue=stats_queue,
                    )
                elif command == CMD_FILESERVER_RESTART:
                    if process_fileserver.is_alive():
                        terminate_process(
                            "file-server", process_fileserver, e_interrupt_fileserver
                        )
                    process_fileserver, e_interrupt_fileserver = start_process(
                        "file-server",
                        fileserver_main,
                        config,
                        directory=fileserver_hdd_dir,
                    )
                    fileserver_enabled = True
                elif command == CMD_FILE_SAVE:
                    flag_keep_current_files()
                else:
                    print("[red]Command not recognized[/red]")
            else:
                e_interrupt.wait(timeout=0.1)

            if not process_inference.is_alive():
                e_interrupt.set()

    except:
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
        except:
            console.print_exception()
    try:
        if process_inference is not None and process_inference.is_alive():
            terminate_process("inference", process_inference, e_interrupt_inference)
    except:
        console.print_exception()
    try:
        if process_fileserver is not None and process_fileserver.is_alive():
            terminate_process("file-server", process_fileserver, e_interrupt_fileserver)
    except:
        console.print_exception()
    try:
        if process_streaming is not None and process_streaming.is_alive():
            terminate_process("streaming", process_streaming, e_interrupt_streaming)
    except:
        console.print_exception()

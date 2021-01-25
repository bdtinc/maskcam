import os
import sys
import time
import json
import signal
import threading
import configparser
import multiprocessing as mp

from rich import print
from rich.console import Console
from datetime import datetime

from common import CONFIG_FILE, USBCAM_PROTOCOL, RASPICAM_PROTOCOL
from common import (
    CMD_FILE_SAVE,
    CMD_STREAMING_START,
    CMD_STREAMING_STOP,
    CMD_INFERENCE_RESTART,
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
console = Console()


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
            "\nMQTT is DISABLED since MQTT_BROKER_IP or MQTT_DEVICE_NAME env vars are not defined\n"
        )
        return None, None
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
        # Should only have 1 element at a time unless this thread gets blocked
        stats_queue = mp.Queue(maxsize=5)
        mqtt_client.on_message = mqtt_process_message

        return mqtt_client, stats_queue


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
    return mqtt_send_msg(
        mqtt_client,
        MQTT_TOPIC_FILES,
        {
            "device_id": MQTT_DEVICE_NAME,
            "file_server": get_ip_address(),
            "file_list": ["file1.txt", "/path/to/file2.mp4"],
        },
        enqueue=False,  # Will be resent on_connect or when something changes
    )


def mqtt_send_statistics(mqtt_client, stats_queue):
    if mqtt_client is None:
        return
    while not stats_queue.empty():
        statistics = stats_queue.get_nowait()
        topic = MQTT_TOPIC_STATS  # TODO: implement MQTT_TOPIC_ALERTS
        message = {"device_id": MQTT_DEVICE_NAME, **statistics}
        mqtt_send_msg(mqtt_client, topic, message, enqueue=True)


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
    try:
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        config.sections()

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

        # Init MQTT or set these to None
        mqtt_client, stats_queue = mqtt_init(config)

        # SIGINT handler (Ctrl+C)
        signal.signal(signal.SIGINT, sigint_handler)
        print("[green bold]Press Ctrl+C to stop all processes[/green bold]")

        process_inference = None
        process_streaming = None
        process_filesave = None
        process_fileserver = None

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

        # Create dir for saved video chunks
        if is_live_input and int(config["maskcam"]["fileserver-enabled"]):
            # Start static fileserver for saved videos
            process_fileserver, e_interrupt_fileserver = start_process(
                "file-server", fileserver_main, config
            )

            # TODO: Implement periodic filesaving
            # output_dir = config["maskcam"]["file-temp-dir"]
            # output_filename = (
            #     f"{output_dir}/{datetime.today().strftime('%Y%m%d_%H%M%S')}.mp4"
            # )
            # # Video file save process
            # process_filesave, e_interrupt_filesave = start_process(
            #     "file-save", filesave_main, config, output_filename=output_filename
            # )

        while not e_interrupt.is_set():
            # Send MQTT statistics
            mqtt_send_statistics(mqtt_client, stats_queue)

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
                else:
                    print("[red]Command not recognized[/red]")
            else:
                e_interrupt.wait(timeout=0.1)

            if not process_inference.is_alive():
                e_interrupt.set()

    except:
        console.print_exception()

    try:
        # If process_inference was not created will throw exception, but process_filesave
        # won't have been created either so it's not important to shut it down.
        if process_inference is not None and process_inference.is_alive():
            terminate_process("inference", process_inference, e_interrupt_inference)
        if process_filesave is not None and process_filesave.is_alive():
            terminate_process("file-save", process_filesave, e_interrupt_fileserver)
        if process_fileserver is not None and process_fileserver.is_alive():
            terminate_process("file-server", process_fileserver, e_interrupt_fileserver)
    except:
        console.print("\n\nAn exception occurred trying to terminate some process")
        console.print_exception()

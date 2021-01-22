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
from paho.mqtt import client as paho_mqtt_client

from common import CONFIG_FILE, USBCAM_PROTOCOL, RASPICAM_PROTOCOL
from utils import get_ip_address
from maskcam_inference import main as inference_main
from maskcam_filesave import main as filesave_main
from maskcam_fileserver import main as fileserver_main
from maskcam_streaming import main as streaming_main


# MQTT topics
MQTT_TOPIC_HELLO = "hello"
MQTT_TOPIC_STATS = "receive-from-jetson"
MQTT_TOPIC_ALERTS = "alerts"
MQTT_TOPIC_FILES = "video-files"

# Must come defined as environment var or MQTT gets disabled
MQTT_BROKER_IP = os.environ.get("MQTT_BROKER_IP", None)
MQTT_DEVICE_NAME = os.environ.get("MQTT_DEVICE_NAME", None)
MQTT_DEVICE_DESCRIPTION = "MaskCam @ Jetson Nano"


# mp.set_start_method("spawn")

# Use threading instead of mp.Event() for sigint_handler, see:
# https://bugs.python.org/issue41606
e_interrupt = threading.Event()

mqtt_msg_queue = mp.Queue(maxsize=100)  # 100 mqtt messages stored max


def sigint_handler(sig, frame):
    print("\n[red]Ctrl+C pressed. Interrupting...[/red]")
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


def mqtt_send_queue(mqtt_client):
    success = True
    while not mqtt_msg_queue.empty() and success:
        q_msg = mqtt_msg_queue.get_nowait()
        print(f"Sending enqueued message to topic: {q_msg['topic']}")
        success = mqtt_send_msg(mqtt_client, q_msg["topic"], q_msg["message"])
    return success


def mqtt_on_connect(client, userdata, flags, code):
    if code == 0:
        print("[green]Connected to MQTT Broker[/green]")
        success = mqtt_say_hello(client)
        success = success and mqtt_send_file_list(client)
        success = success and mqtt_send_queue(client)
        if not success:
            print(f"[red]Failed to send MQTT message after connecting[/red]")
    else:
        print(f"[red]Failed to connect to MQTT[/red], return code {code}\n")


def mqtt_connect_broker(
    client_id: str, broker_ip: str, broker_port: int
) -> paho_mqtt_client:
    client = paho_mqtt_client.Client(client_id)
    client.on_connect = mqtt_on_connect
    client.connect(broker_ip, broker_port)
    return client


def mqtt_send_msg(mqtt_client, topic, message, enqueue=True):
    if mqtt_client is None:
        print(f"Skipping MQTT message to topic: {topic}")
        return False

    # Check previous enqueued msgs
    mqtt_send_queue(mqtt_client)

    result = mqtt_client.publish(topic, json.dumps(message))
    if result[0] == 0:
        console.log(f"{topic} | MQTT message [green]SENT[/green]")
        print(message)
        return True
    else:
        if enqueue:
            if not mqtt_msg_queue.full():
                console.log(f"{topic} | MQTT message [yellow]ENQUEUED[/yellow]")
                mqtt_msg_queue.put_nowait({"topic": topic, "message": message})
            else:
                console.log(f"{topic} | MQTT message [red]DROPPED: FULL QUEUE[/red]")
        else:
            console.log(f"{topic} | MQTT message [yellow]DISCARDED[/yellow]")
        return False


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


def mqtt_init(config):
    if MQTT_BROKER_IP is None or MQTT_DEVICE_NAME is None:
        print(
            "\nMQTT is DISABLED since MQTT_BROKER_IP or MQTT_DEVICE_NAME env vars are not defined\n"
        )
        return None, None
    else:
        mqtt_broker_port = int(config["maskcam"]["mqtt-broker-port"])
        print(f"\nConnecting to MQTT server {MQTT_BROKER_IP}:{mqtt_broker_port}")
        print(f"Device name: {MQTT_DEVICE_NAME}\n\n")
        mqtt_client = mqtt_connect_broker(
            client_id=MQTT_DEVICE_NAME,
            broker_ip=MQTT_BROKER_IP,
            broker_port=mqtt_broker_port,
        )
        mqtt_client.loop_start()
        # Should only have 1 element at a time unless this thread gets blocked
        stats_queue = mp.Queue(maxsize=5)
        return mqtt_client, stats_queue


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
    console = Console()
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

        # TODO: Implement MQTT
        # TODO: Implement streaming
        # TODO: Implement periodic filesaving

        # Create dir for saved video chunks
        if is_live_input and int(config["maskcam"]["fileserver-enabled"]):
            # Start fileserver
            process_fileserver, e_interrupt_fileserver = start_process(
                "file-server", fileserver_main, config
            )
            # output_dir = config["maskcam"]["file-temp-dir"]
            # output_filename = (
            #     f"{output_dir}/{datetime.today().strftime('%Y%m%d_%H%M%S')}.mp4"
            # )
            # # Video file save process
            # process_filesave, e_interrupt_filesave = start_process(
            #     "file-save", filesave_main, config, output_filename=output_filename
            # )

        while not e_interrupt.is_set():
            if not process_inference.is_alive():
                e_interrupt.set()

            # Send MQTT statistics
            mqtt_send_statistics(mqtt_client, stats_queue)

            e_interrupt.wait(timeout=0.5)
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

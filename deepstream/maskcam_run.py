import sys
import signal
import time
import threading
import multiprocessing as mp
import configparser

from rich import print
from rich.console import Console
from datetime import datetime

from common import CAMERA_PROTOCOL, CONFIG_FILE
from maskcam_inference import main as inference_main
from maskcam_filesave import main as filesave_main
from maskcam_streaming import main as streaming_main


# mp.set_start_method("spawn")

# Use threading instead of mp.Event() for sigint_handler, see:
# https://bugs.python.org/issue41606
e_interrupt = threading.Event()


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


if __name__ == "__main__":
    if len(sys.argv) > 2:
        print(
            """Usage: python3 maskcam_run.py [ URI ]
        Examples:
        \t$ python3 maskcam_run.py
        \t$ python3 maskcam_run.py file:///absolute/path/to/file.mp4
        \t$ python3 maskcam_run.py camera:///dev/video1

        Notes:
        \t - If no URI is provided, will use default-input defined in config_maskcam.txt
        \t - If a file:///path/file.mp4 is provided, the output will be output_file.mp4 in the current dir
        \t - If the input is a live camera:///dev/videoX, the output will be consecutive
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

        # Output file name
        is_live_input = CAMERA_PROTOCOL in input_filename
        if is_live_input:
            output_dir = config["maskcam"]["default-output-dir"]
            output_filename = (
                f"{output_dir}/{datetime.today().strftime('%Y%m%d_%H%M%S')}.mp4"
            )
        else:
            output_filename = f"output_{input_filename.split('/')[-1]}"
        print(f"Output file: {output_filename}")

        signal.signal(signal.SIGINT, sigint_handler)
        print("[green bold]Press Ctrl+C to stop all processes[/green bold]")

        # Inference process
        process_inference, e_interrupt_inference = start_process(
            "inference", inference_main, config, input_filename=input_filename
        )

        # TODO: Implement MQTT
        # TODO: Implement streaming
        # TODO: Implement periodic filesaving

        # Video file save process
        process_filesave, e_interrupt_filesave = start_process(
            "file-save", filesave_main, config, output_filename=output_filename
        )

        while not e_interrupt.is_set():
            if not process_inference.is_alive():
                print(f"Inference process has ended, finish all processes")
                e_interrupt.set()
            e_interrupt.wait(timeout=0.5)
    except:
        console.print_exception()

    print("Trying to stop running processes...")
    try:
        # If process_inference was not created will throw exception, but process_filesave
        # won't have been created either so it's not important to shut it down.
        if process_inference.is_alive():
            terminate_process("inference", process_inference, e_interrupt_inference)
        terminate_process("file-save", process_filesave, e_interrupt_filesave)
    except:
        pass

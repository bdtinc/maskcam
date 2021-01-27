from datetime import datetime
from rich import print


def print_process(color, name, *args, error=False, warning=False, **kwargs):
    timestamp = f"{datetime.now():%H:%M:%S}"
    if error:
        print(f"\n[red]{timestamp} | {name} | ERROR: [/red]", *args, "\n")
    elif warning:
        print(f"[yellow]{timestamp} | {name} | WARN: [/yellow]", *args, "\n")
    else:
        print(f"[{color}]{timestamp} | {name} | [/{color}]", *args)


def print_run(*args, **kwargs):
    print_process("blue", "maskcam-run", *args, **kwargs)


def print_fileserver(*args, **kwargs):
    print_process("dark_violet", "file-server", *args, **kwargs)


def print_filesave(*args, **kwargs):
    print_process("dark_magenta", "file-save", *args, **kwargs)


def print_streaming(*args, **kwargs):
    print_process("dark_green", "streaming", *args, **kwargs)


def print_inference(*args, **kwargs):
    print_process("bright_yellow", "inference", *args, **kwargs)


def print_mqtt(*args, **kwargs):
    print_process("bright_green", "mqtt", *args, **kwargs)
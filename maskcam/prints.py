################################################################################
# Copyright (c) 2020-2021, NVIDIA CORPORATION. All rights reserved.
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
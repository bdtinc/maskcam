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

import logging
from rich.logging import RichHandler

logging.basicConfig(
    level="NOTSET",
    format="%(message)s",
    datefmt="|",  # Not needed w/balena, use [%X] otherwise
    handlers=[RichHandler(markup=True)],
)

log = logging.getLogger("rich")


def print_process(
    color, process_name, *args, error=False, warning=False, exception=False, **kwargs
):
    msg = " ".join([str(arg) for arg in args])  # Concatenate all incoming strings or objects
    rich_msg = f"[{color}]{process_name}[/{color}] | {msg}"
    if error:
        log.error(rich_msg)
    elif warning:
        log.warning(rich_msg)
    elif exception:
        log.exception(rich_msg)
    else:
        log.info(rich_msg)


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


def print_common(*args, **kwargs):
    print_process("white", "common", *args, **kwargs)

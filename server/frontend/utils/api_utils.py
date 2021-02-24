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

import json
import os
from typing import Dict, List

import requests

SERVER_URL = os.environ["SERVER_URL"]


def get_devices():
    """
    Get all devices.
    """
    response = requests.get(f"http://{SERVER_URL}/devices")

    devices_json = json.loads(response.content) if response.ok else []

    devices = [None]
    devices.extend([device["id"] for device in devices_json])
    return devices


def get_device(device_id: str):
    """
    Get specific device.

    Arguments:
        device_id {str} -- Device id.
    """
    response = requests.get(f"http://{SERVER_URL}/devices/{device_id}")

    return json.loads(response.content) if response.ok else None


def get_statistics_from_to(device_id, datetime_from, datetime_to):
    """
    Get statistics from a specific device within a datetime range.

    Arguments:
        device_id {str} -- Device id.
        datetime_from {str} -- Datetime from.
        datetime_to {str} -- Datetime to.
    """
    response = requests.get(
        f"http://{SERVER_URL}/devices/{device_id}/statistics?datefrom={datetime_from}&dateto={datetime_to}"
    )

    return json.loads(response.content) if response.ok else None

def get_device_files(device_id):
    """
    Get files from a specific device

    Arguments:
        device_id {str} -- Device id.
    """
    response = requests.get(
        f"http://{SERVER_URL}/files/{device_id}"
    )

    return json.loads(response.content) if response.ok else None


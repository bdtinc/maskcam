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

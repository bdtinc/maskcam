import json
import os
from typing import Dict, List

import requests

SERVER_URL = os.environ["SERVER_URL"]


def get_devices():
    response = requests.get(f"http://{SERVER_URL}/devices")

    return json.loads(response.content) if response.ok else []


def get_device(device_id: str):
    response = requests.get(f"http://{SERVER_URL}/devices/{device_id}")

    return json.loads(response.content) if response.ok else None


def get_statistics_from_to(device_id, datetime_from, datetime_to):
    response = requests.get(
        f"http://{SERVER_URL}/devices/{device_id}/statistics?datefrom={datetime_from}&dateto={datetime_to}"
    )

    return json.loads(response.content) if response.ok else None

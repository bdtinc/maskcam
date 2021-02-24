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

import os
import json
from multiprocessing import Queue
from typing import Callable, List
from paho.mqtt import client as paho_mqtt_client

from .config import config
from .prints import print_mqtt as print

# MQTT topics
MQTT_TOPIC_HELLO = "hello"
MQTT_TOPIC_UPDATE = "device-status"
MQTT_TOPIC_STATS = "receive-from-jetson"
MQTT_TOPIC_ALERTS = "alerts"
MQTT_TOPIC_FILES = "video-files"
MQTT_TOPIC_COMMANDS = "commands"

config_broker_ip = config["mqtt"]["mqtt-broker-ip"].strip()
config_device_name = config["mqtt"]["mqtt-device-name"].strip()

# Must come defined or MQTT gets disabled
MQTT_BROKER_IP = None
if config_broker_ip and config_broker_ip != "0":
    MQTT_BROKER_IP = config_broker_ip

MQTT_DEVICE_NAME = None
if config_device_name and config_device_name != "0":
    MQTT_DEVICE_NAME = config_device_name

MQTT_BROKER_PORT = int(config["mqtt"]["mqtt-broker-port"])
MQTT_DEVICE_DESCRIPTION = config["mqtt"]["mqtt-device-description"]

mqtt_msg_queue = Queue(maxsize=100)  # 100 mqtt messages stored max


def mqtt_send_queue(mqtt_client):
    success = True
    while not mqtt_msg_queue.empty() and success:
        q_msg = mqtt_msg_queue.get_nowait()
        print(f"Sending enqueued message to topic: {q_msg['topic']}")
        success = mqtt_send_msg(mqtt_client, q_msg["topic"], q_msg["message"])
    return success


def mqtt_connect_broker(
    client_id: str,
    broker_ip: str,
    broker_port: int,
    subscribe_to: List[List] = None,
    cb_success: Callable = None,
) -> paho_mqtt_client:
    def cb_on_connect(client, userdata, flags, code):
        if code == 0:
            print("[green]Connected to MQTT Broker[/green]")
            if subscribe_to:
                print("Subscribing to topics:")
                print(subscribe_to)
                client.subscribe(subscribe_to)  # Always re-suscribe after reconnecting
            if cb_success is not None:
                cb_success(client)
            if not mqtt_send_queue(client):
                print(f"Failed to send MQTT message queue after connecting", warning=True)
        else:
            print(f"Failed to connect to MQTT[/red], return code {code}", warning=True)

    def cb_on_disconnect(client, userdata, code):
        print(f"Disconnected from MQTT Broker, code: {code}")

    client = paho_mqtt_client.Client(client_id)
    client.on_connect = cb_on_connect
    client.on_disconnect = cb_on_disconnect
    client.connect(broker_ip, broker_port)
    client.loop_start()
    return client


def mqtt_send_msg(mqtt_client, topic, message, enqueue=True):
    if mqtt_client is None:
        print(f"MQTT not connected. Skipping message to topic: {topic}")
        return False

    # Check previous enqueued msgs
    mqtt_send_queue(mqtt_client)

    result = mqtt_client.publish(topic, json.dumps(message))
    if result[0] == 0:
        print(f"{topic} | MQTT message [green]SENT[/green]")
        print(message)
        return True
    else:
        if enqueue:
            if not mqtt_msg_queue.full():
                print(f"{topic} | MQTT message [yellow]ENQUEUED[/yellow]")
                mqtt_msg_queue.put_nowait({"topic": topic, "message": message})
            else:
                print(f"{topic} | MQTT message [red]DROPPED: FULL QUEUE[/red]", error=True)
        else:
            print(f"{topic} | MQTT message [yellow]DISCARDED[/yellow]", warning=True)
        return False

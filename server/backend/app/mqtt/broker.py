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

from app.core.config import MQTT_BROKER, MQTT_BROKER_PORT
from paho.mqtt import client as mqtt_client
from typing import Callable


def connect_mqtt_broker(client_id: str, cb_connect: Callable=None) -> mqtt_client:
    """
    Connect to MQTT broker.

    Arguments:
        client_id {str} -- Client process id.
        cb_connect {Callable} -- Callback for on_connect

    Returns:
        mqtt_client -- MQTT client.
    """

    def on_connect(client, userdata, flags, code):
        if code == 0:
            print("Connected to MQTT Broker")
            if cb_connect is not None:
                cb_connect(client)
        else:
            print(f"Failed to connect, return code {code}\n")

    def on_disconnect(client, userdata, code):
        print("MQTT Broker disconnected")

    client = mqtt_client.Client(client_id)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.connect(MQTT_BROKER, MQTT_BROKER_PORT)
    return client

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

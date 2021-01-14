import os
from paho.mqtt import client as mqtt_client

MQTT_BROKER = os.environ["MQTT_BROKER"]
MQTT_BROKER_PORT = 1883


def connect_mqtt_broker(client_id: str) -> mqtt_client:
    def on_connect(client, userdata, flags, code):
        if code == 0:
            print("Connected to MQTT Broker")
        else:
            print(f"Failed to connect, return code {code}\n")

    client = mqtt_client.Client(client_id)
    client.on_connect = on_connect
    client.connect(MQTT_BROKER, MQTT_BROKER_PORT)
    return client

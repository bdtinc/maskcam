from app.core.config import MQTT_BROKER, MQTT_BROKER_PORT, MQTT_CLIENT_TOPICS
from paho.mqtt import client as mqtt_client


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

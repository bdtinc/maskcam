import json

from broker import connect_mqtt_broker
from paho.mqtt import client as mqtt_client


def subscribe(client: mqtt_client):
    def on_message(client, userdata, msg):
        message = json.loads(msg.payload.decode())
        topic = msg.topic
        print(f"Message received in topic: {topic}")
        print(message)

    test_topic = "test"
    client.subscribe(test_topic)
    client.on_message = on_message


def main():
    client = connect_mqtt_broker(client_id=f"subscriber-test")
    subscribe(client)
    client.loop_forever()


if __name__ == "__main__":
    main()

import random
import time
import json
from datetime import datetime

from paho.mqtt import client as mqtt_client


broker = "localhost"
port = 1883

# generate client ID with pub prefix randomly
client_id = f"python-mqtt-{random.randint(0, 1000)}"


def connect_mqtt():
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)

    client = mqtt_client.Client(client_id)
    client.on_connect = on_connect
    client.connect(broker, port)
    return client


def publish(client):
    msg_count = 0
    while True:
        time.sleep(5)

        device_id = f"device_{msg_count}"

        # Test hello
        topic = "hello"
        hello_msg = {
            "id": device_id,
            "description": f"message {msg_count}",
        }
        hello_result = client.publish(topic, json.dumps(hello_msg))

        if hello_result[0] == 0:
            print(f"Send `{hello_msg}` to topic `{topic}`")
        else:
            print(f"Failed to send message to topic {topic}")

        # Test alert
        time.sleep(2)
        topic = "alerts"
        people_with_mask = random.randint(0, 1000)
        people_without_mask = random.randint(0, 1000)

        alert_msg = {
            "device_id": device_id,
            "timestamp": datetime.timestamp(datetime.now()),
            "people_with_mask": people_with_mask,
            "people_without_mask": people_without_mask,
            "people_total": people_with_mask + people_without_mask,
        }

        alert_result = client.publish(topic, json.dumps(alert_msg))

        if alert_result[0] == 0:
            print(f"Send `{alert_msg}` to topic `{topic}`")
        else:
            print(f"Failed to send message to topic {topic}")

        # Test report
        time.sleep(2)
        topic = "receive-from-jetson"
        people_with_mask = random.randint(0, 1000)
        people_without_mask = random.randint(0, 1000)

        report_msg = {
            "device_id": device_id,
            "timestamp": datetime.timestamp(datetime.now()),
            "people_with_mask": people_with_mask,
            "people_without_mask": people_without_mask,
            "people_total": people_with_mask + people_without_mask,
        }

        report_result = client.publish(topic, json.dumps(report_msg))

        if report_result[0] == 0:
            print(f"Send `{report_msg}` to topic `{topic}`")
        else:
            print(f"Failed to send message to topic {topic}")

        msg_count += 1


def run():
    client = connect_mqtt()
    client.loop_start()
    publish(client)


if __name__ == "__main__":
    run()

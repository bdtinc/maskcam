import json
import random
import time
from datetime import datetime, timezone, timedelta
from paho.mqtt import client as mqtt_client


def publish(client):
    for msg_count in range(0, 6):
        time.sleep(1)

        device_id = f"Device_{msg_count}"

        # Test hello
        topic = "hello"
        hello_msg = {
            "id": device_id,
            "description": f"Description {msg_count}",
        }
        hello_result = client.publish(topic, json.dumps(hello_msg))

        if hello_result[0] == 0:
            print(f"Send `{hello_msg}` to topic `{topic}`")
        else:
            print(f"Failed to send message to topic {topic}")

        # Test alert
        time.sleep(1)
        topics = ["alerts", "receive-from-jetson"]
        now = datetime.now(timezone.utc)
        for _ in range(0, 600):
            topic = random.choice(topics)
            if topic == "alerts":
                people_with_mask = random.randint(2000, 3000)
                people_without_mask = random.randint(0, 1000)
            else:
                people_with_mask = random.randint(0, 1000)
                people_without_mask = random.randint(500, 1000)

            alert_msg = {
                "device_id": device_id,
                "timestamp": datetime.timestamp(now),
                "people_with_mask": people_with_mask,
                "people_without_mask": people_without_mask,
                "people_total": people_with_mask + people_without_mask,
            }

            result = client.publish(topic, json.dumps(alert_msg))

            if result[0] == 0:
                print(f"Send `{alert_msg}` to topic `{topic}`")
            else:
                print(f"Failed to send message to topic {topic}")

            now += timedelta(minutes=1)


def connect_mqtt_broker(client_id: str):
    def on_connect(client, userdata, flags, code):
        if code == 0:
            print("Connected to MQTT Broker")
        else:
            print(f"Failed to connect, return code {code}\n")

    client = mqtt_client.Client(client_id)
    client.on_connect = on_connect
    # client.connect("3.17.17.197", 1883)
    client.connect("0.0.0.0", 1883)
    return client


def run():
    client = connect_mqtt_broker(client_id=f"publisher-{random.randint(0, 10)}")
    client.loop_start()
    publish(client)


if __name__ == "__main__":
    run()

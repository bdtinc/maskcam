import json
import random
import time
from datetime import datetime

from broker import connect_mqtt_broker


def publish(client):
    msg_count = 0
    while True:
        time.sleep(1)

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
        time.sleep(1)
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
        time.sleep(1)
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
    client = connect_mqtt_broker(client_id=f"publisher-{random.randint(0, 10)}")
    client.loop_start()
    publish(client)


if __name__ == "__main__":
    run()

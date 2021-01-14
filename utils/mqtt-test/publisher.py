import json
import random
import time
from datetime import datetime, timezone

from broker import connect_mqtt_broker


def publish(client):
    while True:
        time.sleep(1)

        # Test topic
        test_topic = "test"
        test_result = client.publish(
            test_topic,
            json.dumps(
                {
                    "msg": f"testing",
                    "timestamp": datetime.timestamp(datetime.now(timezone.utc)),
                }
            ),
        )

        if test_result[0] == 0:
            print(f"Send test msg to test topic")
        else:
            print(f"Failed to send message to test topic")


def run():
    client = connect_mqtt_broker(client_id=f"publisher-test")
    client.loop_start()
    publish(client)


if __name__ == "__main__":
    run()

import json
from datetime import datetime

from app.core.config import MQTT_CLIENT_TOPICS, SUSCRIBER_CLIENT_ID
from app.db.cruds import create_device, create_statistic
from app.db.utils import StatisticTypeEnum
from paho.mqtt import client as mqtt_client
from sqlalchemy.exc import IntegrityError

from broker import connect_mqtt_broker


def subscribe(client: mqtt_client):
    def on_message(client, userdata, msg):
        process_message(msg)

    client.subscribe(MQTT_CLIENT_TOPICS)
    client.on_message = on_message


def process_message(msg):
    message = json.loads(msg.payload.decode())

    topic = msg.topic
    if topic == "hello":
        # Register new Jetson device
        device_id = message["id"]

        try:
            device = create_device(
                device_id=device_id,
                description=message["description"],
            )
            print("Added device")
        except IntegrityError:
            print(f"Error, a device with id={device_id} already exist")

    elif topic in ["alerts", "receive-from-jetson"]:
        try:
            # Receive alert or report and save it to the database
            statistic = create_statistic(
                device_id=message["device_id"],
                datetime=datetime.fromtimestamp(message["timestamp"]),
                statistic_type=(
                    StatisticTypeEnum.ALERT
                    if topic in "alerts"
                    else StatisticTypeEnum.REPORT
                ),
                people_with_mask=message["people_with_mask"],
                people_without_mask=message["people_without_mask"],
                people_total=message["people_total"],
            )

            print(f"Added statistic")
        except IntegrityError:
            print(f"Error, the statistic already exist")

    elif topic == "send-to-jetson":
        print(f"Send info")


def main():
    client = connect_mqtt_broker(client_id=SUSCRIBER_CLIENT_ID)
    subscribe(client)
    client.loop_forever()


if __name__ == "__main__":
    main()

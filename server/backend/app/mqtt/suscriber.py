import json
from datetime import datetime

from app.core.config import (
    MQTT_BROKER,
    MQTT_BROKER_PORT,
    MQTT_CLIENT_TOPICS,
    SUSCRIBER_CLIENT_ID,
)
from app.db.cruds import create_device, create_statistic
from app.db.utils import StatisticTypeEnum

from paho.mqtt import client as mqtt_client
from sqlalchemy.exc import IntegrityError


def connect_mqtt() -> mqtt_client:
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)

    client = mqtt_client.Client(SUSCRIBER_CLIENT_ID)
    client.on_connect = on_connect
    client.connect(MQTT_BROKER, MQTT_BROKER_PORT)
    return client


def subscribe(client: mqtt_client):
    def on_message(client, userdata, msg):
        message = json.loads(msg.payload.decode())

        if msg.topic == "hello":
            # Register new Jetson device
            device_id = message["id"]

            try:
                device = create_device(
                    device_id=device_id,
                    description=message["description"],
                )
                print("Device added")
            except IntegrityError:
                print(f"Error, a device with id={device_id} already exist")

        elif msg.topic in ["alerts", "receive-from-jetson"]:
            # Receive alert or report and save it to the database
            statistic = create_statistic(
                device_id=message["device_id"],
                datetime=datetime.fromtimestamp(message["timestamp"]),
                statistic_type=(
                    StatisticTypeEnum.ALERT
                    if msg.topic in "alerts"
                    else StatisticTypeEnum.REPORT
                ),
                people_with_mask=message["people_with_mask"],
                people_without_mask=message["people_without_mask"],
                people_total=message["people_total"],
            )

            print(f"Register statistic")

        elif msg.topic == "send-to-jetson":
            print(f"Send info")

    client.subscribe(MQTT_CLIENT_TOPICS)
    client.on_message = on_message


def main():
    client = connect_mqtt()
    subscribe(client)
    client.loop_forever()


if __name__ == "__main__":
    main()

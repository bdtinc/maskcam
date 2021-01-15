import json

from app.core.config import MQTT_CLIENT_TOPICS, SUBSCRIBER_CLIENT_ID
from app.db.cruds import create_device, create_statistic
from app.db.schema import get_db_session
from app.db.utils import convert_timestamp_to_datetime, get_enum_type
from broker import connect_mqtt_broker

from paho.mqtt import client as mqtt_client
from sqlalchemy.exc import IntegrityError


def subscribe(client: mqtt_client):
    """
    Subscribe client to topic.

    Arguments:
        client {mqtt_client} -- Client process id.
    """

    def on_message(client, userdata, msg):
        database_session = get_db_session()
        try:
            process_message(database_session, msg)
        finally:
            database_session.close()

    client.subscribe(MQTT_CLIENT_TOPICS)
    client.on_message = on_message


def process_message(database_session, msg):
    """
    Process message sent to topic.

    Arguments:
        database_session {Session} -- Database session.
        msg {str} -- Received message.
    """
    message = json.loads(msg.payload.decode())

    topic = msg.topic
    if topic == "hello":
        # Register new Jetson device
        device_id = message["id"]

        try:
            device_information = {
                "id": device_id,
                "description": message["description"],
            }
            device = create_device(
                db_session=database_session,
                device_information=device_information,
            )
            print("Added device")
        except IntegrityError:
            print(f"Error, a device with id={device_id} already exist")

    elif topic in ["alerts", "receive-from-jetson"]:
        try:
            # Receive alert or report and save it to the database
            statistic_information = {
                "device_id": message["device_id"],
                "datetime": convert_timestamp_to_datetime(message["timestamp"]),
                "statistic_type": get_enum_type(topic),
                "people_with_mask": message["people_with_mask"],
                "people_without_mask": message["people_without_mask"],
                "people_total": message["people_total"],
            }

            statistic = create_statistic(
                db_session=database_session,
                statistic_information=statistic_information,
            )

            print(f"Added statistic")
        except IntegrityError:
            print(f"Error, the statistic already exist")

    elif topic == "send-to-jetson":
        print(f"Send info")


def main():
    client = connect_mqtt_broker(client_id=SUBSCRIBER_CLIENT_ID)
    subscribe(client)
    client.loop_forever()


if __name__ == "__main__":
    main()

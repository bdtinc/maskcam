################################################################################
# Copyright (c) 2020-2021, Berkeley Design Technology, Inc. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
################################################################################

import json

from app.core.config import SUBSCRIBER_CLIENT_ID, MQTT_HELLO_TOPIC,\
                            MQTT_ALERT_TOPIC, MQTT_SEND_TOPIC,\
                            MQTT_REPORT_TOPIC, MQTT_FILES_TOPIC
from app.db.cruds import create_device, create_statistic, update_files, update_device
from app.db.schema import get_db_session
from app.db.utils import convert_timestamp_to_datetime, get_enum_type
from broker import connect_mqtt_broker

from paho.mqtt import client as mqtt_client
from sqlalchemy.exc import IntegrityError

MQTT_CLIENT_TOPICS = [  # topic, QoS
    (MQTT_HELLO_TOPIC, 2),
    (MQTT_FILES_TOPIC, 2),
    (MQTT_ALERT_TOPIC, 2),
    (MQTT_REPORT_TOPIC, 2),
    (MQTT_SEND_TOPIC, 2),
]

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
        device_id = message["device_id"]

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
            print(f"A device with id={device_id} already exists")

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
    
    elif topic == "video-files":
        try:
            print(f"Adding files for device_id: {message['device_id']}")
            new_information = {"file_server_address": message["file_server"]}
            update_device(db_session=database_session, device_id=message["device_id"], new_device_information=new_information)
            update_files(db_session=database_session, device_id=message["device_id"], file_list=message["file_list"])
        except Exception as e:
            print(f"Exception trying to update files: {e}")

    elif topic == "send-to-jetson":
        # Just monitoring this channel, useful for debugging
        print(f"Detected info sent to device_id: {message['device_id']}")


def main():
    client = connect_mqtt_broker(client_id=SUBSCRIBER_CLIENT_ID, cb_connect=subscribe)
    client.loop_forever()


if __name__ == "__main__":
    main()

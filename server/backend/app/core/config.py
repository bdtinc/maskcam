import os

# Database configuration
DB_USER = os.environ["POSTGRES_USER"]
DB_PASSWORD = os.environ["POSTGRES_PASSWORD"]
DB_NAME = os.environ["POSTGRES_DB"]
DB_PORT = os.environ["POSTGRES_PORT"]
DB_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@db:{DB_PORT}/{DB_NAME}"

# MQTT broker configuration
MQTT_BROKER = os.environ["MQTT_BROKER"]
MQTT_BROKER_PORT = int(os.environ["MQTT_BROKER_PORT"])

# MQTT subscriber configuration
SUBSCRIBER_CLIENT_ID = os.environ["SUBSCRIBER_CLIENT_ID"]

# Topic configuration
MQTT_HELLO_TOPIC = "hello"
MQTT_ALERT_TOPIC = "alerts"
MQTT_REPORT_TOPIC = "receive-from-jetson"
MQTT_SEND_TOPIC = "send-to-jetson"
MQTT_FILES_TOPIC = "video-files"

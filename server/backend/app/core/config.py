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

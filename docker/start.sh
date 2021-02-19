#!/usr/bin/env bash
nvargus-daemon &

echo
echo "Provided input:"
echo " - MASKCAM_INPUT = $MASKCAM_INPUT"
echo "Device Address:"
echo " - MASKCAM_DEVICE_ADDRESS = $MASKCAM_DEVICE_ADDRESS"
echo "Development mode:"
echo " - DEV_MODE = $DEV_MODE"
echo
echo "MQTT configuration:"
echo " - MQTT_BROKER_IP = $MQTT_BROKER_IP"
echo " - MQTT_DEVICE_NAME = $MQTT_DEVICE_NAME"
echo

if [[ $DEV_MODE -eq 1 ]]; then
    echo "Development mode enabled, exec maskcam_run.py manually"
    /bin/bash
else
    ./maskcam_run.py $MASKCAM_INPUT
fi

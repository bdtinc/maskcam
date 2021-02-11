#!/usr/bin/env bash
nvargus-daemon &

echo
echo "Maskcam env vars provided: "
echo " - MASCAM_INPUT = $MASKCAM_INPUT"
echo " - MQTT_BROKER_IP = $MQTT_BROKER_IP"
echo " - MQTT_DEVICE_NAME = $MQTT_DEVICE_NAME"
echo " - DEV_MODE = $DEV_MODE"
echo

if [[ $DEV_MODE -eq 1 ]]; then
    echo "Development mode enabled, exec maskcam_run.py manually"
    sleep infinity
else
    ./maskcam_run.py $MASKCAM_INPUT
fi

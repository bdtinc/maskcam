import os
import json

import pandas as pd
import streamlit as st

from datetime import datetime, time, timezone
from session_manager import get_state
from utils.api_utils import get_device, get_devices, get_statistics_from_to, get_device_files
from utils.format_utils import create_chart, format_data

from paho.mqtt import publish as mqtt_publish

MQTT_BROKER = os.environ["MQTT_BROKER"]
MQTT_BROKER_PORT = int(os.environ["MQTT_BROKER_PORT"])
MQTT_CLIENT_ID = os.environ["MQTT_CLIENT_ID"]

MQTT_TOPIC_COMMANDS = "commands"
CMD_FILE_SAVE = "save_file"
CMD_STREAMING_START = "streaming_start"
CMD_STREAMING_STOP = "streaming_stop"
CMD_INFERENCE_RESTART = "inference_restart"
CMD_FILESERVER_RESTART = "fileserver_restart"


def display_sidebar(all_devices, state):
    """
    Display sidebar information.
    """
    st.sidebar.subheader("Device selection")
    state.selected_device = st.sidebar.selectbox(
        "Selected device",
        all_devices,
        index=all_devices.index(
            state.selected_device if state.selected_device else None
        ),
    )

    st.sidebar.subheader("Filters")
    state.date_filter = st.sidebar.date_input(
        "From date - To date",
        (
            state.date_filter[0]
            if state.date_filter and len(state.date_filter) == 2
            else datetime.now(timezone.utc),
            state.date_filter[1]
            if state.date_filter and len(state.date_filter) == 2
            else datetime.now(timezone.utc),
        ),
    )
    first_column, second_column = st.sidebar.beta_columns(2)
    state.from_time = first_column.time_input(
        "From time", state.from_time if state.from_time else time(0, 0)
    )
    state.to_time = second_column.time_input(
        "To time", state.to_time if state.to_time else time(23, 45)
    )

    state.group_data_by = st.sidebar.selectbox(
        "Group data by",
        ["Second", "Minute", "Hour", "Day", "Week", "Month"],
        index=2,
    )

    state.show_only_one_chart = st.sidebar.checkbox(
        "Show only one chart", value=True
    )


def display_device(state):
    """
    Display specific device information.
    """
    selected_device = state.selected_device
    device = get_device(selected_device)

    if device is None:
        st.write(
            "Seems that something went wrong while getting the device information, please select another device."
        )
    else:
        st.header("General information")
        st.markdown(f'**Id:** {device["id"]}')
        st.markdown(f'**Description:** {device["description"]}')
        mqtt_status = st.empty()
        cols = st.beta_columns(6)
        # Buttons from right to left
        with cols.pop():
            if st.button("Restart Deepstream"):
                send_mqtt_command(device["id"], CMD_INFERENCE_RESTART, mqtt_status)
        with cols.pop():
            if st.button("Restart file server"):
                send_mqtt_command(device["id"], CMD_FILESERVER_RESTART, mqtt_status)
        with cols.pop():
            if st.button("Stop streaming"):
                send_mqtt_command(device["id"], CMD_STREAMING_STOP, mqtt_status)
        with cols.pop():
            if st.button("Start streaming"):
                send_mqtt_command(device["id"], CMD_STREAMING_START, mqtt_status)
        with cols.pop():
            if st.button("Save a video"):
                send_mqtt_command(device["id"], CMD_FILE_SAVE, mqtt_status)
        with cols.pop():
            if st.button("Refresh page"):
                # Force frontend to refresh
                pass

        st.header("Statistics")
        device_statistics = None
        date_filter = state.date_filter

        if len(date_filter) == 2:
            datetime_from = f"{date_filter[0]}T{state.from_time}"
            datetime_to = f"{date_filter[1]}T{state.to_time}"
            device_statistics = get_statistics_from_to(
                selected_device, datetime_from, datetime_to
            )

        if not device_statistics:
            st.write(
                "The selected device has no statistics to show for the given filters."
            )
        else:
            reports, alerts = format_data(
                device_statistics, state.group_data_by
            )

            if state.show_only_one_chart:
                complete_chart = create_chart(reports=reports, alerts=alerts)
                st.plotly_chart(complete_chart, use_container_width=True)
            else:
                st.subheader("Reports")
                if reports:
                    report_chart = create_chart(reports=reports)
                    st.plotly_chart(report_chart, use_container_width=True)
                else:
                    st.write(
                        "The selected device has no reports to show for the given filters."
                    )

                st.subheader("Alerts")
                if alerts:
                    alerts_chart = create_chart(alerts=alerts)
                    st.plotly_chart(alerts_chart, use_container_width=True)
                else:
                    st.write(
                        "The selected device has no alerts to show for the given filters."
                    )
        device_files = get_device_files(device_id=selected_device)
        st.subheader("Saved video files on device")
        if not device_files:
            st.write("The selected device has no saved files yet")
        else:
            for file_instance in device_files:
                url = f"{device['file_server_address']}/{file_instance['video_name']}"
                st.markdown(f"[{file_instance['video_name']}]({url})")
                # Adding download attribute won't work anyway on chrome
                # st.markdown(f"<a href=\"{url}\" download=\"{file_instance['video_name']}\""
                #             f" target=\"_blank\">{file_instance['video_name']}</a>",
                #             unsafe_allow_html=True)


def mqtt_set_status(mqtt_status, text):
    mqtt_status.markdown(f"**MQTT status:** {text}")

def send_mqtt_message(topic, message, mqtt_status):
    try:
        mqtt_publish.single(topic,
                            json.dumps(message),
                            hostname=MQTT_BROKER,
                            port=MQTT_BROKER_PORT,
                            client_id=MQTT_CLIENT_ID)
        mqtt_set_status(mqtt_status, "Message sent")
        return True
    except Exception as e:
        mqtt_set_status(mqtt_status, f"Could not send MQTT message to broker: {e}")
        return False

def send_mqtt_command(device_id, command, mqtt_status):
    send_mqtt_message(MQTT_TOPIC_COMMANDS, {"device_id": device_id, "command": command}, mqtt_status)


def main():
    state = get_state()
    st.set_page_config(page_title="Maskcam")

    st.title("MaskCam device")
    all_devices = get_devices()
    display_sidebar(all_devices, state)

    if state.selected_device is None:
        st.write("Please select a device.")
    else:
        display_device(state)

    state.sync()


if __name__ == "__main__":
    main()

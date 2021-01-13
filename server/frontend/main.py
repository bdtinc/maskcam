from datetime import datetime, time, timezone

import pandas as pd
import streamlit as st

from session_manager import get_state
from utils.api_utils import get_device, get_devices, get_statistics_from_to
from utils.format_utils import create_chart, format_data


def display_device(
    selected_device, date_filter, from_time, to_time, group_data_by
):
    device = get_device(selected_device)

    if device is None:
        st.write(
            "Seems that something went wrong while getting the device information, please select another device."
        )
    else:
        st.header("General information")
        st.markdown(f'**Id:** {device["id"]}')
        st.markdown(f'**Description:** {device["description"]}')

        st.header("Statistics")
        device_statistics = None
        if len(date_filter) == 2:
            datetime_from = f"{date_filter[0]}T{from_time}"
            datetime_to = f"{date_filter[1]}T{to_time}"
            device_statistics = get_statistics_from_to(
                selected_device, datetime_from, datetime_to
            )

        if not device_statistics:
            st.write(
                "The selected device has no statistics to show for the given filters."
            )
        else:
            reports, alerts = format_data(device_statistics, group_data_by)

            st.subheader("Reports")
            if reports:
                report_chart = create_chart(reports)
                st.plotly_chart(report_chart, use_container_width=True)
            else:
                st.write(
                    "The selected device has no reports to show for the given filters."
                )

            st.subheader("Alerts")
            if alerts:
                alerts_chart = create_chart(alerts)
                st.plotly_chart(alerts_chart, use_container_width=True)
            else:
                st.write(
                    "The selected device has no alerts to show for the given filters."
                )


def get_all_devices():
    devices = [None]
    devices.extend([device["id"] for device in get_devices()])
    return devices


def build_sidebar(all_devices, state):
    st.sidebar.subheader("Device selection")
    state.selected_device = st.sidebar.selectbox(
        "Selected device",
        all_devices,
        index=all_devices.index(
            state.selected_device if state.selected_device else None
        ),
    )

    st.sidebar.subheader("Filters")
    date_filter = st.sidebar.date_input(
        "From date - To date",
        (
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
        ),
    )
    first_column, second_column = st.sidebar.beta_columns(2)
    from_time = first_column.time_input("From time", time(0, 0))
    to_time = second_column.time_input("To time", time(23, 45))

    group_data_by = st.sidebar.selectbox(
        "Group data by",
        ["Minute", "Hour", "Day", "Week", "Month"],
        index=1,
    )

    return date_filter, from_time, to_time, group_data_by


def main():
    st.set_page_config(page_title="Maskcam")

    state = get_state()
    st.title("MaskCam device")
    all_devices = get_all_devices()
    date_filter, from_time, to_time, group_data_by = build_sidebar(
        all_devices, state
    )

    if state.selected_device is None:
        st.write("Please select a device.")
    else:
        display_device(
            state.selected_device,
            date_filter,
            from_time,
            to_time,
            group_data_by,
        )

    state.sync()


if __name__ == "__main__":
    main()

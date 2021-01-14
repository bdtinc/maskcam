from datetime import datetime, time, timezone

import pandas as pd
import streamlit as st

from session_manager import get_state
from utils.api_utils import get_device, get_devices, get_statistics_from_to
from utils.format_utils import create_chart, format_data


def display_sidebar(all_devices, state):
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
            if state.date_filter
            else datetime.now(timezone.utc),
            state.date_filter[1]
            if state.date_filter
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
        ["Minute", "Hour", "Day", "Week", "Month"],
        index=1,
    )

    state.show_only_one_chart = st.sidebar.checkbox(
        "Show only one chart", value=True
    )


def display_device(state):
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


def main():
    st.set_page_config(page_title="Maskcam")

    state = get_state()
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

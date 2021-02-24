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

from typing import Dict, List

import pandas as pd
import numpy as np

import plotly.graph_objects as go
from plotly.subplots import make_subplots


def format_data(statistics: List = [], group_data_by: str = None):
    """
    Format data to be displayed in the carts.

    Arguments:
        statistics {List} -- All device statistics.
        group_data_by {str} -- User selected aggregation option.
    """
    reports, alerts = {}, {}

    for statistic in statistics:
        # Separate reports from alerts
        if statistic["statistic_type"] == "REPORT":
            if not reports:
                reports = create_statistics_dict()

            reports = add_information(reports, statistic)
        else:
            if not alerts:
                alerts = create_statistics_dict()

            alerts = add_information(alerts, statistic)

    # Aggregate data
    if reports:
        reports = group_data(reports, group_data_by)

    if alerts:
        alerts = group_data(alerts, group_data_by)

    return reports, alerts


def group_data(data: Dict, group_data_by: str):
    """
    Aggregate data using different criteria.

    Arguments:
        data {Dict} -- Data to aggregate.
        group_data_by {str} -- User selected aggregation option.
    """
    data_df = pd.DataFrame.from_dict(data)
    data_df["dates"] = pd.to_datetime(data_df["dates"])

    criterion = "H"
    if group_data_by == "Second":
        criterion = "S"
    elif group_data_by == "Minute":
        criterion = "T"
    elif group_data_by == "Day":
        criterion = "D"
    elif group_data_by == "Week":
        criterion = "W"
    elif group_data_by == "Month":
        criterion = "M"

    group = (
        data_df.resample(criterion, on="dates")
        .agg(
            {
                "people_total": "sum",
                "people_with_mask": "sum",
                "people_without_mask": "sum",
            }
        )
        .reset_index()
    )

    # Calculate new mask percentage
    group["mask_percentage"] = (
        group["people_with_mask"] * 100 / group["people_total"]
    )
    group["mask_percentage"] = group["mask_percentage"].replace(
        [np.inf, -np.inf], 0
    )

    group["visible_people"] = (
        group["people_with_mask"] + group["people_without_mask"]
    )

    # Drop empty lines
    group.dropna(subset=["mask_percentage"], inplace=True)
    group = group.to_dict()
    grouped_data = {
        "dates": [t.to_pydatetime() for t in group["dates"].values()],
        "people_with_mask": list(group["people_with_mask"].values()),
        "people_total": list(group["people_total"].values()),
        "mask_percentage": list(group["mask_percentage"].values()),
        "visible_people": list(group["visible_people"].values()),
    }

    return grouped_data


def create_statistics_dict():
    """
    Chart data structure.
    """
    return {
        "dates": [],
        "mask_percentage": [],
        "people_total": [],
        "people_with_mask": [],
        "people_without_mask": [],
        "visible_people": [],
    }


def add_information(statistic_dict: Dict, statistic_information: Dict):
    """
    Add information to existing dict.

    Arguments:
        statistic_dict {Dict} -- Existing dict.
        statistic_information {Dict} -- Data to add.
    """
    statistic_dict["dates"].append(statistic_information["datetime"])

    total = statistic_information["people_total"]
    people_with_mask = statistic_information["people_with_mask"]
    people_without_mask = statistic_information["people_without_mask"]

    statistic_dict["people_total"].append(total)
    statistic_dict["people_with_mask"].append(people_with_mask)
    statistic_dict["people_without_mask"].append(people_without_mask)

    mask_percentage = (
        statistic_information["people_with_mask"] * 100 / total
        if total != 0
        else 0
    )
    statistic_dict["mask_percentage"].append(mask_percentage)

    statistic_dict["visible_people"].append(
        people_with_mask + people_without_mask
    )

    return statistic_dict


def create_chart(reports: Dict = {}, alerts: Dict = {}):
    """
    Create Plotly chart.

    Arguments:
        reports {Dict} -- Reports data.
        alerts {Dict} -- Alerts data.
    """

    # Create figure with secondary y-axis
    figure = make_subplots(specs=[[{"secondary_y": True}]])

    if reports:
        report_colors = {
            "people_total": "darkslategray",
            "people_with_mask": "cadetblue",
            "mask_percentage": "limegreen",
            "visible_people": "royalblue",
        }
        figure = add_trace(reports, figure, report_colors, trace_type="report")

    if alerts:
        alert_colors = {
            "people_total": "darkred",
            "people_with_mask": "salmon",
            "mask_percentage": "orange",
            "visible_people": "indianred",
        }
        figure = add_trace(alerts, figure, alert_colors, trace_type="alert")

    # Set x-axis title
    figure.update_xaxes(title_text="Datetime")

    # Set y-axes titles
    figure.update_yaxes(title_text="Number of people", secondary_y=False)
    figure.update_yaxes(
        title_text="Mask Percentage", secondary_y=True, rangemode="tozero"
    )
    figure.update_layout(
        xaxis_tickformat="%H:%M:%S <br> %Y/%d/%m",
        barmode="group",
        bargap=0.4,
        bargroupgap=0.1,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
        margin=dict(t=50, b=30, r=30),
        font=dict(
            size=10,
        ),
    )

    return figure


def add_trace(trace_information: Dict, figure, colors: Dict, trace_type=""):
    """
    Add new trace to Plotly chart.

    Arguments:
        trace_information {Dict} -- Trace to add.
        figure -- Plotly chart.
        colors {Dict} -- Colors to use in the new trace.
        trace_type -- Alert or Report.
    """
    figure.add_trace(
        go.Bar(
            x=trace_information["dates"],
            y=trace_information["people_total"],
            name="People" if not trace_type else f"People {trace_type}",
            marker_color=colors["people_total"],
        ),
        secondary_y=False,
    )

    figure.add_trace(
        go.Bar(
            x=trace_information["dates"],
            y=trace_information["people_with_mask"],
            name="Masks" if not trace_type else f"Masks {trace_type}",
            marker_color=colors["people_with_mask"],
        ),
        secondary_y=False,
    )

    figure.add_trace(
        go.Bar(
            x=trace_information["dates"],
            y=trace_information["visible_people"],
            name="Visible" if not trace_type else f"Visible {trace_type}",
            marker_color=colors["visible_people"],
        ),
        secondary_y=False,
    )

    figure.add_trace(
        go.Scatter(
            x=trace_information["dates"],
            y=trace_information["mask_percentage"],
            name="Mask %" if not trace_type else f"Mask % {trace_type}",
            marker_color=colors["mask_percentage"],
        ),
        secondary_y=True,
    )

    return figure

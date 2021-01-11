from datetime import datetime, timezone

from .enums import StatisticTypeEnum


def convert_timestamp_to_datetime(timestamp: float):
    return datetime.fromtimestamp(timestamp, timezone.utc)


def get_enum_type(statistic_type: str):
    return (
        StatisticTypeEnum.ALERT
        if statistic_type.lower() == "alert"
        else StatisticTypeEnum.REPORT
    )

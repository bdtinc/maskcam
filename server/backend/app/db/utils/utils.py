from datetime import datetime, timezone

from .enums import StatisticTypeEnum


def convert_timestamp_to_datetime(timestamp: float) -> datetime:
    """
    Convert timestamp date format to datetime.

    Arguments:
        timestamp {float} -- Input timestamp.

    Returns:
        datetime -- Datetime formatted object which represents the
        same information as timestamp.
    """
    return datetime.fromtimestamp(timestamp, timezone.utc)


def get_enum_type(statistic_type: str) -> StatisticTypeEnum:
    """
    Convert string object to enum.

    Arguments:
        statistic_type {str} -- Input string.

    Returns:
        StatisticTypeEnum -- Enum corresponding to statistic_type.
    """
    return (
        StatisticTypeEnum.ALERT
        if statistic_type.lower() == "alerts"
        else StatisticTypeEnum.REPORT
    )

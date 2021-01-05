import datetime
from typing import Dict, List, Optional, Union

from app.db.schema import StatisticsModel, database_session
from app.db.utils import StatisticTypeEnum

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound


def create_statistic(
    device_id: str,
    datetime: datetime,
    statistic_type: StatisticTypeEnum,
    people_with_mask: int,
    people_without_mask: int,
    people_total: int,
) -> Union[StatisticsModel, IntegrityError]:
    """
    Register new statistic entry.

    Arguments:
        device_id {str} -- Jetson id which sent the information.
        datetime {datetime} -- Datetime when the device registered the information.
        statistic_type {StatisticTypeEnum} -- Type of information (ALERT or REPORT).
        people_with_mask {int} -- Quantity of people using a face mask.
        people_without_mask {int} -- Quantity of people not using a face mask.
        people_total {int} -- Total quantity of people registered by the device.

    Returns:
        Union[StatisticsModel, IntegrityError] -- Statistic instance that was added
        to the database or an exception in case a statistic already exists.

    """
    try:
        statistic = StatisticsModel(
            device_id=device_id,
            datetime=datetime,
            statistic_type=statistic_type,
            people_with_mask=people_with_mask,
            people_without_mask=people_without_mask,
            people_total=people_total,
        )

        database_session.add(statistic)
        database_session.commit()
        database_session.refresh(statistic)
        return statistic

    except IntegrityError:
        database_session.rollback()
        raise


def get_statistic(
    device_id: str, datetime: datetime
) -> Union[StatisticsModel, NoResultFound]:
    """
    Get a specific statistic.

    Arguments:
        device_id {str} -- Jetson id which sent the information.
        datetime {datetime} -- Datetime when the device registered the information.

    Returns:
        Union[StatisticsModel, NoResultFound] -- Statistic instance defined by device_id and datetime
        or an exception in case there's no matching statistic.

    """
    try:
        return get_statistic_by_id_and_datetime(device_id, datetime)

    except NoResultFound:
        raise


def get_statistics() -> List[StatisticsModel]:
    """
    Get all statistics.

    Returns:
        List[StatisticsModel] -- All statistic instances present in the database.

    """
    return database_session.query(StatisticsModel).all()


def update_statistic(
    device_id: str, datetime: datetime, new_statistic_information: Dict = {}
) -> Union[StatisticsModel, NoResultFound]:
    """
    Modify a specific statistic.

    Arguments:
        device_id {str} -- Jetson id which sent the information.
        datetime {datetime} -- Datetime when the device registered the information.

    Returns:
        Union[StatisticsModel, NoResultFound] -- Updated statistic instance defined by device_id
        and datetime or an exception in case there's no matching statistic.

    """
    try:
        statistic = get_statistic_by_id_and_datetime(device_id, datetime)

        for key, value in new_statistic_information.items():
            if hasattr(statistic, key):
                setattr(statistic, key, value)

        database_session.commit()
        return statistic

    except NoResultFound:
        raise


def delete_statistic(
    device_id: str, datetime: datetime
) -> Union[StatisticsModel, NoResultFound]:
    """
    Delete a specific statistic.

    Arguments:
        device_id {str} -- Jetson id which sent the information.
        datetime {datetime} -- Datetime when the device registered the information.

    Returns:
        Union[StatisticsModel, NoResultFound] -- Statistic instance that was deleted
        or an exception in case there's no matching statistic.

    """
    try:
        statistic = get_statistic_by_id_and_datetime(device_id, datetime)
        database_session.delete(statistic)
        database_session.commit()
        return statistic

    except NoResultFound:
        raise


def get_statistic_by_id_and_datetime(
    device_id: str, datetime: datetime
) -> Union[StatisticsModel, NoResultFound]:
    """
    Get a device using the table's primary keys.

    Arguments:
        device_id {str} -- Jetson id which sent the information.
        datetime {datetime} -- Datetime when the device registered the information.

    Returns:
        Union[StatisticsModel, NoResultFound] -- Statistic instance defined by device_id and
        datetime or an exception in case there's no matching statistic.

    """
    statistic = database_session.query(StatisticsModel).get(
        (device_id, datetime)
    )

    if not statistic:
        raise NoResultFound()

    return statistic

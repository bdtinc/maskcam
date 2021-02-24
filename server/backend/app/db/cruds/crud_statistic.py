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

from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from app.db.schema import StatisticsModel

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound


def create_statistic(
    db_session: Session, statistic_information: Dict = {}
) -> Union[StatisticsModel, IntegrityError]:
    """
    Register new statistic entry.

    Arguments:
        db_session {Session} -- Database session.
        statistic_information {Dict} -- New statistic information.

    Returns:
        Union[StatisticsModel, IntegrityError] -- Statistic instance that was added
        to the database or an exception in case a statistic already exists.
    """
    try:
        statistic = StatisticsModel(**statistic_information)
        db_session.add(statistic)
        db_session.commit()
        db_session.refresh(statistic)
        return statistic

    except IntegrityError:
        db_session.rollback()
        raise


def get_statistic(
    db_session: Session, device_id: str, datetime: datetime
) -> Union[StatisticsModel, NoResultFound]:
    """
    Get a specific statistic.

    Arguments:
        db_session {Session} -- Database session.
        device_id {str} -- Jetson id which sent the information.
        datetime {datetime} -- Datetime when the device registered the information.

    Returns:
        Union[StatisticsModel, NoResultFound] -- Statistic instance defined by device_id and datetime
        or an exception in case there's no matching statistic.
    """
    try:
        return get_statistic_by_id_and_datetime(db_session, device_id, datetime)

    except NoResultFound:
        raise


def get_statistics(
    db_session: Session, device_id: Optional[str] = None
) -> List[StatisticsModel]:
    """
    Get all statistics.

    Arguments:
        db_session {Session} -- Database session.
        device_id {Optional[str]} -- Device id.

    Returns:
        List[StatisticsModel] -- All statistic instances present in the database or
        all statistics from a specific device.
    """
    if device_id:
        # Get all statistics from a specific device
        query = db_session.query(StatisticsModel)
        return query.filter(StatisticsModel.device_id == device_id).all()

    else:
        # Get all statistics from form the database
        return db_session.query(StatisticsModel).all()


def get_statistics_from_to(
    db_session: Session,
    device_id: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> List[StatisticsModel]:
    """
    Get all statistics within a datetime range.

    Arguments:
        db_session {Session} -- Database session.
        device_id {str} -- Device id.
        from_date {Optional[str]} -- Beginning of datetime range.
        to_date {Optional[str]} -- End of datetime range.

    Returns:
        List[StatisticsModel] -- All statistic instances present in the database
        within a given datetime range.
    """
    query = db_session.query(StatisticsModel)
    query = query.filter(StatisticsModel.device_id == device_id)

    if to_date is None:
        # By default, show information until the current day
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    if from_date:
        return query.filter(
            StatisticsModel.datetime.between(from_date, to_date)
        ).all()

    return query.filter(StatisticsModel.datetime <= to_date).all()


def update_statistic(
    db_session: Session,
    device_id: str,
    datetime: datetime,
    new_statistic_information: Dict = {},
) -> Union[StatisticsModel, NoResultFound]:
    """
    Modify a specific statistic.

    Arguments:
        db_session {Session} -- Database session.
        device_id {str} -- Jetson id which sent the information.
        datetime {datetime} -- Datetime when the device registered the information.
        new_statistic_information {Dict} -- New statistic information.

    Returns:
        Union[StatisticsModel, NoResultFound] -- Updated statistic instance defined by device_id
        and datetime or an exception in case there's no matching statistic.
    """
    try:
        try:
            # Remove device id as it can't be modified
            del new_statistic_information["device_id"]
        except KeyError:
            pass

        try:
            # Remove datetime as it can't be modified
            del new_statistic_information["datetime"]
        except KeyError:
            pass

        statistic = get_statistic_by_id_and_datetime(
            db_session, device_id, datetime
        )

        for key, value in new_statistic_information.items():
            if hasattr(statistic, key):
                setattr(statistic, key, value)

        db_session.commit()
        return statistic

    except NoResultFound:
        raise


def delete_statistic(
    db_session: Session, device_id: str, datetime: datetime
) -> Union[StatisticsModel, NoResultFound]:
    """
    Delete a specific statistic.

    Arguments:
        db_session {Session} -- Database session.
        device_id {str} -- Jetson id which sent the information.
        datetime {datetime} -- Datetime when the device registered the information.

    Returns:
        Union[StatisticsModel, NoResultFound] -- Statistic instance that was deleted
        or an exception in case there's no matching statistic.
    """
    try:
        statistic = get_statistic_by_id_and_datetime(
            db_session, device_id, datetime
        )
        db_session.delete(statistic)
        db_session.commit()
        return statistic

    except NoResultFound:
        raise


def get_statistic_by_id_and_datetime(
    db_session: Session, device_id: str, datetime: datetime
) -> Union[StatisticsModel, NoResultFound]:
    """
    Get a statistic using the table's primary keys.

    Arguments:
        db_session {Session} -- Database session.
        device_id {str} -- Jetson id which sent the information.
        datetime {datetime} -- Datetime when the device registered the information.

    Returns:
        Union[StatisticsModel, NoResultFound] -- Statistic instance defined by device_id and
        datetime or an exception in case there's no matching statistic.
    """
    statistic = db_session.query(StatisticsModel).get((device_id, datetime))

    if not statistic:
        raise NoResultFound()

    return statistic

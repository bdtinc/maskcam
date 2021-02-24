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

from typing import Dict, List, Optional

from app.api import GenericException, ItemAlreadyExist, NoItemFoundException
from app.db.cruds import (
    create_statistic,
    delete_statistic,
    get_statistic,
    get_statistics,
    get_statistics_from_to,
    update_statistic,
)
from app.db.schema import StatisticSchema, get_db_generator
from app.db.utils import convert_timestamp_to_datetime, get_enum_type

from fastapi import APIRouter, Depends, Query
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

statistic_router = APIRouter()


@statistic_router.post(
    "/devices/{device_id}/statistics", response_model=StatisticSchema
)
def create_statistic_item(
    device_id: str,
    statistic_information: Dict = {},
    db: Session = Depends(get_db_generator),
):
    """
    Create new statistic entry.

    Arguments:
        device_id {str} -- Device id which sent the statistic.
        statistic_information {Dict} -- New statistic information.
        db {Session} -- Database session.

    Returns:
        Union[StatisticSchema, ItemAlreadyExist] -- Statistic instance that was added
        to the database or an exception in case a statistic already exists.
    """
    try:
        # Format input data
        statistic_information["device_id"] = device_id
        statistic_information["datetime"] = convert_timestamp_to_datetime(
            statistic_information["datetime"]
        )
        statistic_information["statistic_type"] = get_enum_type(
            statistic_information["statistic_type"]
        )

        return create_statistic(
            db_session=db, statistic_information=statistic_information
        )
    except IntegrityError:
        raise ItemAlreadyExist()


@statistic_router.get(
    "/devices/{device_id}/statistics/{timestamp}",
    response_model=StatisticSchema,
)
def get_statistic_item(
    device_id: str,
    timestamp: float,
    db: Session = Depends(get_db_generator),
):
    """
    Get a specific statistic.

    Arguments:
        device_id {str} -- Device id.
        timestamp {float} -- Timestamp when the device registered the information.
        db {Session} -- Database session.

    Returns:
        Union[StatisticSchema, NoItemFoundException] -- Statistic instance defined by device_id and
        timestamp or an exception in case there's no matching statistic.
    """
    try:
        return get_statistic(
            db_session=db,
            device_id=device_id,
            datetime=convert_timestamp_to_datetime(timestamp),
        )
    except NoResultFound:
        raise NoItemFoundException()


@statistic_router.get(
    "/devices/{device_id}/statistics",
    response_model=List[StatisticSchema],
)
def get_all_device_statistics_items(
    device_id: str,
    datefrom: Optional[str] = Query(None),
    dateto: Optional[str] = Query(None),
    timestampfrom: Optional[float] = Query(None),
    timestampto: Optional[float] = Query(None),
    db: Session = Depends(get_db_generator),
):
    """
    Get all statistics of a specific device.

    Arguments:
        device_id {str} -- Device id.
        datefrom {Optional[str]} -- Datetime to show information from.
        dateto {Optional[str]} -- Datetime to show information to.
        timestampfrom {Optional[float]} -- Timestamp to show information from.
        timestampto {Optional[float]} -- Timestamp to show information from.
        db {Session} -- Database session.

    Returns:
        List[StatisticSchema] -- Statistic instances defined by device_id and
        datetime range.
    """
    from_datetime = datefrom
    to_datetime = dateto

    if not from_datetime and timestampfrom:
        from_datetime = convert_timestamp_to_datetime(timestampfrom)

    if not to_datetime and timestampto:
        to_datetime = convert_timestamp_to_datetime(timestampto)

    return get_statistics_from_to(
        db_session=db,
        device_id=device_id,
        from_date=from_datetime,
        to_date=to_datetime,
    )


@statistic_router.get(
    "/statistics",
    response_model=List[StatisticSchema],
)
def get_all_statistics_items(db: Session = Depends(get_db_generator)):
    """
    Get all statistics from all devices.

    Arguments:
        db {Session} -- Database session.

    Returns:
        List[StatisticSchema] -- All statistic instances present in the database.
    """
    return get_statistics(db_session=db)


@statistic_router.put(
    "/devices/{device_id}/statistics/{timestamp}",
    response_model=StatisticSchema,
)
def update_statistic_item(
    device_id: str,
    timestamp: float,
    new_statistic_information: Dict = {},
    db: Session = Depends(get_db_generator),
):
    """
    Modify a specific statistic.

    Arguments:
        device_id {str} -- Device id.
        timestamp {float} -- Timestamp when the device registered the information.
        new_statistic_information {Dict} -- New statistic information.
        db {Session} -- Database session.

    Returns:
        Union[StatisticSchema, NoItemFoundException, GenericException] -- Updated statistic
        instance defined by device_id and datetime or an exception in case there's no
        matching statistic.
    """
    try:
        return update_statistic(
            db_session=db,
            device_id=device_id,
            datetime=convert_timestamp_to_datetime(timestamp),
            new_statistic_information=new_statistic_information,
        )

    except NoResultFound:
        raise NoItemFoundException()
    except DataError as e:
        raise GenericException(e)


@statistic_router.delete(
    "/devices/{device_id}/statistics/{timestamp}",
    response_model=StatisticSchema,
)
def delete_statistic_item(
    device_id: str,
    timestamp: float,
    db: Session = Depends(get_db_generator),
):
    """
    Delete a specific statistic.

    Arguments:
        device_id {str} -- Device id.
        timestamp {float} -- Timestamp when the device registered the information.
        db {Session} -- Database session.

    Returns:
        Union[StatisticSchema, NoItemFoundException, GenericException] -- Statistic instance
        that was deleted or an exception in case there's no matching statistic.
    """
    try:
        return delete_statistic(
            db_session=db,
            device_id=device_id,
            datetime=convert_timestamp_to_datetime(timestamp),
        )

    except NoResultFound:
        raise NoItemFoundException()
    except DataError as e:
        raise GenericException(e)

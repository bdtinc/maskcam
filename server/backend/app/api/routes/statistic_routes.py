from typing import Optional, List, Dict

from fastapi import APIRouter, Depends, Query
from app.db.utils import (
    convert_timestamp_to_datetime,
    get_enum_type,
)
from datetime import datetime

from app.db.cruds import (
    get_statistic,
    get_statistics,
    update_statistic,
    create_statistic,
    delete_statistic,
    get_statistics_from_to,
)
from app.db.schema import (
    StatisticSchema,
    get_db_generator,
)
from sqlalchemy.orm import Session
from app.api import NoItemFoundException, GenericException, ItemAlreadyExist
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import IntegrityError, DataError

statistic_router = APIRouter()


@statistic_router.post(
    "/devices/{device_id}/statistics", response_model=StatisticSchema
)
def create_statistic_item(
    device_id: str,
    statistic_information: Dict = {},
    db: Session = Depends(get_db_generator),
):
    try:
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
    # response_model=List[StatisticSchema],
)
def get_all_device_statistics_items(
    device_id: str,
    datefrom: Optional[str] = Query(None),
    dateto: Optional[str] = Query(None),
    timestampfrom: Optional[float] = Query(None),
    timestampto: Optional[float] = Query(None),
    db: Session = Depends(get_db_generator),
):
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

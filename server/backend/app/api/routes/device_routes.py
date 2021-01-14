from typing import Optional, List, Dict

from fastapi import APIRouter, Depends

from app.db.cruds import (
    get_device,
    get_devices,
    update_device,
    create_device,
    delete_device,
)
from app.db.schema import (
    DeviceSchema,
    get_db_generator,
)
from sqlalchemy.orm import Session
from fastapi.encoders import jsonable_encoder
from app.api import NoItemFoundException, GenericException, ItemAlreadyExist
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import IntegrityError, DataError

device_router = APIRouter()


@device_router.post("/devices", response_model=DeviceSchema)
def create_device_item(
    device_information: DeviceSchema,
    db: Session = Depends(get_db_generator),
):
    try:
        device_information = jsonable_encoder(device_information)
        return create_device(
            db_session=db, device_information=device_information
        )
    except IntegrityError:
        raise ItemAlreadyExist()


@device_router.get("/devices/{device_id}", response_model=DeviceSchema)
def get_device_item(
    device_id: str,
    db: Session = Depends(get_db_generator),
):
    try:
        return get_device(db_session=db, device_id=device_id)
    except NoResultFound:
        raise NoItemFoundException()


@device_router.get(
    "/devices",
    response_model=List[DeviceSchema],
    response_model_include={"id", "description"},
)
def get_devices_items(db: Session = Depends(get_db_generator)):
    return get_devices(db_session=db)


@device_router.put("/devices/{device_id}", response_model=DeviceSchema)
def update_device_item(
    device_id: str,
    new_device_information: Dict = {},
    db: Session = Depends(get_db_generator),
):
    try:
        return update_device(
            db_session=db,
            device_id=device_id,
            new_device_information=new_device_information,
        )
    except NoResultFound:
        raise NoItemFoundException()
    except DataError as e:
        raise GenericException(e)


@device_router.delete("/devices/{device_id}", response_model=DeviceSchema)
def delete_device_item(
    device_id: str,
    db: Session = Depends(get_db_generator),
):
    try:
        return delete_device(db_session=db, device_id=device_id)
    except NoResultFound:
        raise NoItemFoundException()
    except DataError as e:
        raise GenericException(e)

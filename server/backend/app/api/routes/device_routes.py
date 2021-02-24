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
    create_device,
    delete_device,
    get_device,
    get_devices,
    update_device,
    get_files_by_device
)
from app.db.schema import DeviceSchema, VideoFileSchema, get_db_generator
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

device_router = APIRouter()


@device_router.post("/devices", response_model=DeviceSchema)
def create_device_item(
    device_information: DeviceSchema,
    db: Session = Depends(get_db_generator),
):
    """
    Create device.

    Arguments:
        device_information {DeviceSchema} -- New device information.
        db {Session} -- Database session.

    Returns:
        Union[DeviceSchema, ItemAlreadyExist] -- Device instance that was added
        to the database or an error in case the device already exists.
    """
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
    """
    Get existing device.

    Arguments:
        device_id {str} -- Device id.
        db {Session} -- Database session.

    Returns:
        Union[DeviceSchema, NoItemFoundException] -- Device instance which id is device_id
        or an exception in case there's no matching device.

    """
    try:
        return get_device(db_session=db, device_id=device_id)
    except NoResultFound:
        raise NoItemFoundException()


@device_router.get(
    "/devices",
    response_model=List[DeviceSchema],
    response_model_include={"id", "description", "file_server_address"},
)
def get_devices_items(db: Session = Depends(get_db_generator)):
    """
    Get all existing devices.

    Arguments:
        db {Session} -- Database session.

    Returns:
        List[DeviceSchema] -- All device instances present in the database.
    """
    return get_devices(db_session=db)


@device_router.put("/devices/{device_id}", response_model=DeviceSchema)
def update_device_item(
    device_id: str,
    new_device_information: Dict = {},
    db: Session = Depends(get_db_generator),
):
    """
    Modify a device.

    Arguments:
        device_id {str} -- Device id.
        new_device_information {Dict} -- New device information.
        db {Session} -- Database session.

    Returns:
        Union[DeviceSchema, NoItemFoundException, GenericException] -- Device instance
        which id is device_id or an exception in case there's no matching device.
    """
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
    """
    Delete a device.

    Arguments:
        device_id {str} -- Device id.
        db {Session} -- Database session.

    Returns:
        Union[DeviceSchema, NoItemFoundException, GenericException] -- Device instance that
        was deleted or an exception in case there's no matching device.
    """
    try:
        return delete_device(db_session=db, device_id=device_id)
    except NoResultFound:
        raise NoItemFoundException()
    except DataError as e:
        raise GenericException(e)


@device_router.get("/files/{device_id}", response_model=List[VideoFileSchema])
def get_device_files(
    device_id: str,
    db: Session = Depends(get_db_generator),
):
    """
    Get existing video files in device.

    Arguments:
        device_id {str} -- Device id.
        db {Session} -- Database session.

    Returns:
        List[VideoFileSchema] -- VideoFile instances which device_id matches
    """
    return get_files_by_device(db_session=db, device_id=device_id)

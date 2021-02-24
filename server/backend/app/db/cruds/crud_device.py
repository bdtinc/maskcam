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

from typing import List, Union, Dict

from app.db.schema import DeviceModel

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound


def create_device(
    db_session: Session, device_information: Dict = {}
) -> Union[DeviceModel, IntegrityError]:
    """
    Register new Jetson device.

    Arguments:
        db_session {Session} -- Database session.
        device_information {Dict} -- New device information.

    Returns:
        Union[DeviceModel, IntegrityError] -- Device instance that was added
        to the database or an exception in case the device already exists.
    """
    try:
        # Replace empty spaces in device id
        device_information["id"] = device_information["id"].replace(" ", "_")

        # Create device
        device = DeviceModel(**device_information)
        db_session.add(device)
        db_session.commit()
        db_session.refresh(device)
        return device

    except IntegrityError:
        db_session.rollback()
        raise


def get_device(
    db_session: Session, device_id: str
) -> Union[DeviceModel, NoResultFound]:
    """
    Get a specific device.

    Arguments:
        db_session {Session} -- Database session.
        device_id {str} -- Jetson id.

    Returns:
        Union[DeviceModel, NoResultFound] -- Device instance which id is device_id
        or an exception in case there's no matching device.
    """
    try:
        return get_device_by_id(db_session, device_id)

    except NoResultFound:
        raise


def get_devices(db_session: Session) -> List[DeviceModel]:
    """
    Get all devices.

    Arguments:
        db_session {Session} -- Database session.

    Returns:
        List[DeviceModel] -- All device instances present in the database.
    """
    return db_session.query(DeviceModel).all()


def update_device(
    db_session: Session, device_id: str, new_device_information: Dict = {}
) -> Union[DeviceModel, NoResultFound]:
    """
    Modify a specific Jetson device.

    Arguments:
        db_session {Session} -- Database session.
        device_id {str} -- Jetson id.
        new_device_information {Dict} -- New device information.

    Returns:
        Union[DeviceModel, NoResultFound] -- Device instance which id is device_id
        or an exception in case there's no matching device.
    """
    try:
        try:
            # Remove device id as it can't be modified
            del new_device_information["id"]
        except KeyError:
            pass

        device = get_device_by_id(db_session, device_id)

        for key, value in new_device_information.items():
            if hasattr(device, key):
                setattr(device, key, value)

        db_session.commit()
        return device

    except NoResultFound:
        raise


def delete_device(
    db_session: Session, device_id: str
) -> Union[DeviceModel, NoResultFound]:
    """
    Delete a device.

    Arguments:
        db_session {Session} -- Database session.
        device_id {str} -- Jetson id.

    Returns:
        Union[DeviceModel, NoResultFound] -- Device instance that was deleted
        or an exception in case there's no matching device.

    """
    try:
        device = get_device_by_id(db_session, device_id)
        db_session.delete(device)
        db_session.commit()
        return device

    except NoResultFound:
        raise


def get_device_by_id(
    db_session: Session, device_id: str
) -> Union[DeviceModel, NoResultFound]:
    """
    Get a device using the table's primary key.

    Arguments:
        db_session {Session} -- Database session.
        device_id {str} -- Jetson id.

    Returns:
        Union[DeviceModel, NoResultFound] -- Device instance which id is device_id
        or an exception in case there's no matching device.

    """
    device = db_session.query(DeviceModel).get(device_id)

    if not device:
        raise NoResultFound()

    return device

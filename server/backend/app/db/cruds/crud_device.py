from typing import Optional, Union, List

from app.db.schema import DeviceModel, database_session

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound


def create_device(
    device_id: str, description: Optional[str] = ""
) -> Union[DeviceModel, IntegrityError]:
    """
    Register new Jetson device.

    Arguments:
        device_id {str} -- Jetson id.
        description {Optional[str]} -- Jetson description.

    Returns:
        Union[DeviceModel, IntegrityError] -- Device instance that was added
        to the database or an exception in case the device already exists.

    """
    try:
        device = DeviceModel(id=device_id, description=description)
        database_session.add(device)
        database_session.commit()
        database_session.refresh(device)
        return device

    except IntegrityError:
        database_session.rollback()
        raise


def get_device(device_id: str) -> Union[DeviceModel, NoResultFound]:
    """
    Get a specific device.

    Arguments:
        device_id {str} -- Jetson id.

    Returns:
        Union[DeviceModel, NoResultFound] -- Device instance which id is device_id
        or an exception in case there's no matching device.

    """
    try:
        return get_device_by_id(device_id)

    except NoResultFound:
        raise


def get_devices() -> List[DeviceModel]:
    """
    Get all devices.

    Returns:
        List[DeviceModel] -- All device instances present in the database.

    """
    return database_session.query(DeviceModel).all()


def update_device(
    device_id: str, description: str
) -> Union[DeviceModel, NoResultFound]:
    """
    Modify a specific Jetson device.

    Arguments:
        device_id {str} -- Jetson id.
        description {str} -- New device description.

    Returns:
        Union[DeviceModel, NoResultFound] -- Device instance which id is device_id
        or an exception in case there's no matching device.

    """
    try:
        device = get_device_by_id(device_id)
        device.description = description
        database_session.commit()
        return device

    except NoResultFound:
        # database_session.rollback()
        raise


def delete_device(device_id: str) -> Union[DeviceModel, NoResultFound]:
    """
    Delete a device.

    Arguments:
        device_id {str} -- Jetson id.

    Returns:
        Union[DeviceModel, NoResultFound] -- Device instance that was deleted
        or an exception in case there's no matching device.

    """
    try:
        device = get_device_by_id(device_id)
        database_session.delete(device)
        database_session.commit()
        return device

    except NoResultFound:
        # database_session.rollback()
        raise


def get_device_by_id(device_id: str) -> Union[DeviceModel, NoResultFound]:
    """
    Get a device using the table's primary key.

    Arguments:
        device_id {str} -- Jetson id.

    Returns:
        Union[DeviceModel, NoResultFound] -- Device instance which id is device_id
        or an exception in case there's no matching device.

    """
    device = database_session.query(DeviceModel).get(device_id)

    if not device:
        raise NoResultFound()

    return device

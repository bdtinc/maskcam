import random
from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound

from app.db.cruds import (
    create_device,
    create_statistic,
    delete_device,
    get_device,
    get_devices,
    get_statistic,
    get_statistics,
    update_device,
    update_statistic,
    delete_statistic,
)
from app.db.utils import StatisticTypeEnum

DEVICE_ID = "test"

# Device
def test_create_device():
    device = create_device(
        device_id=DEVICE_ID,
        description="test description",
    )

    assert device.id == DEVICE_ID
    assert device.description == "test description"


def test_create_same_device():
    with pytest.raises(IntegrityError):
        create_device(
            device_id=DEVICE_ID,
            description="test description",
        )


def test_get_device():
    device = get_device(device_id=DEVICE_ID)

    assert device.id == DEVICE_ID
    assert device.description == "test description"


def test_update_device():
    device = update_device(device_id=DEVICE_ID, description="new description")

    assert device.id == DEVICE_ID
    assert device.description == "new description"


# Statistics
def test_create_statistic():
    people_with_mask = 4
    people_without_mask = 7
    now = datetime(2021, 1, 4, 17, 22, 51, 514455)

    statistic = create_statistic(
        device_id=DEVICE_ID,
        datetime=now,
        statistic_type=StatisticTypeEnum.ALERT,
        people_with_mask=people_with_mask,
        people_without_mask=people_without_mask,
        people_total=people_with_mask + people_without_mask,
    )

    assert statistic.device_id == DEVICE_ID
    assert statistic.datetime == now
    assert statistic.statistic_type == StatisticTypeEnum.ALERT
    assert statistic.people_with_mask == people_with_mask
    assert statistic.people_without_mask == people_without_mask
    assert statistic.people_total == people_with_mask + people_without_mask


def test_create_same_statistic():
    people_with_mask = 4
    people_without_mask = 7
    now = datetime(2021, 1, 4, 17, 22, 51, 514455)

    with pytest.raises(IntegrityError):
        create_statistic(
            device_id=DEVICE_ID,
            datetime=now,
            statistic_type=StatisticTypeEnum.ALERT,
            people_with_mask=people_with_mask,
            people_without_mask=people_without_mask,
            people_total=people_with_mask + people_without_mask,
        )


def test_create_another_statistic():
    people_with_mask = 5
    people_without_mask = 8
    now = datetime(2021, 1, 5, 17, 22, 51, 514455)

    statistic = create_statistic(
        device_id=DEVICE_ID,
        datetime=now,
        statistic_type=StatisticTypeEnum.ALERT,
        people_with_mask=people_with_mask,
        people_without_mask=people_without_mask,
        people_total=people_with_mask + people_without_mask,
    )

    assert statistic.device_id == DEVICE_ID
    assert statistic.datetime == now
    assert statistic.statistic_type == StatisticTypeEnum.ALERT
    assert statistic.people_with_mask == people_with_mask
    assert statistic.people_without_mask == people_without_mask
    assert statistic.people_total == people_with_mask + people_without_mask


def test_get_statistic():
    people_with_mask = 4
    people_without_mask = 7
    now = datetime(2021, 1, 4, 17, 22, 51, 514455)

    statistic = get_statistic(device_id=DEVICE_ID, datetime=now)

    assert statistic.device_id == DEVICE_ID
    assert statistic.datetime == now
    assert statistic.statistic_type == StatisticTypeEnum.ALERT
    assert statistic.people_with_mask == people_with_mask
    assert statistic.people_without_mask == people_without_mask
    assert statistic.people_total == people_with_mask + people_without_mask


def test_update_statistic():
    people_without_mask = 7
    now = datetime(2021, 1, 4, 17, 22, 51, 514455)

    statistic = update_statistic(
        device_id=DEVICE_ID,
        datetime=now,
        new_statistic_information={"people_with_mask": 20, "people_total": 27},
    )

    assert statistic.device_id == DEVICE_ID
    assert statistic.datetime == now
    assert statistic.statistic_type == StatisticTypeEnum.ALERT
    assert statistic.people_with_mask == 20
    assert statistic.people_without_mask == people_without_mask
    assert statistic.people_total == 27


def test_delete_statistic():
    people_with_mask = 20
    people_without_mask = 7
    now = datetime(2021, 1, 4, 17, 22, 51, 514455)

    statistic = delete_statistic(
        device_id=DEVICE_ID,
        datetime=now,
    )

    assert statistic.device_id == DEVICE_ID
    assert statistic.datetime == now
    assert statistic.statistic_type == StatisticTypeEnum.ALERT
    assert statistic.people_with_mask == people_with_mask
    assert statistic.people_without_mask == people_without_mask
    assert statistic.people_total == people_with_mask + people_without_mask


def test_delete_device():
    device = delete_device(device_id=DEVICE_ID)

    assert device.id == DEVICE_ID
    assert device.description == "new description"


def test_get_deleted_device():
    with pytest.raises(NoResultFound):
        get_device(device_id=DEVICE_ID)


def test_update_deleted_device():
    with pytest.raises(NoResultFound):
        update_device(device_id=DEVICE_ID, description="new test description")


def test_get_devices():
    devices = get_devices()

    assert devices == []


def test_get_devices():
    stats = get_statistics()

    assert stats == []

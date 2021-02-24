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

import random
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound

from app.db.cruds import (
    create_device,
    create_statistic,
    delete_device,
    delete_statistic,
    get_device,
    get_devices,
    get_statistic,
    get_statistics,
    update_device,
    update_statistic,
)
from app.db.schema import get_db_session
from app.db.utils import StatisticTypeEnum, convert_timestamp_to_datetime

DEVICE_ID = "test"
database_session = get_db_session()

# Device
def test_create_device():
    info = {
        "id": DEVICE_ID,
        "description": "test description",
    }
    device = create_device(db_session=database_session, device_information=info)

    assert device.id == DEVICE_ID
    assert device.description == "test description"


def test_create_device_more_fields():
    with pytest.raises(TypeError):
        info = {
            "id": DEVICE_ID,
            "description": "test description",
            "test_field_1": 1,
            "test_field_2": 2,
        }
        create_device(db_session=database_session, device_information=info)


def test_create_same_device():
    with pytest.raises(IntegrityError):
        info = {
            "id": DEVICE_ID,
            "description": "test description",
        }
        device = create_device(
            db_session=database_session, device_information=info
        )


def test_get_device():
    device = get_device(db_session=database_session, device_id=DEVICE_ID)

    assert device.id == DEVICE_ID
    assert device.description == "test description"


def test_update_device():
    device = update_device(
        db_session=database_session,
        device_id=DEVICE_ID,
        new_device_information={"description": "new description"},
    )

    assert device.id == DEVICE_ID
    assert device.description == "new description"


# Statistics
def test_create_statistic():
    people_with_mask = 4
    people_without_mask = 7
    now = convert_timestamp_to_datetime(1609780971.514455)
    # now = datetime(2021, 1, 4, 17, 22, 51, 514455, tzinfo=timezone.utc)

    stat_info = {
        "device_id": DEVICE_ID,
        "datetime": now,
        "statistic_type": StatisticTypeEnum.ALERT,
        "people_with_mask": people_with_mask,
        "people_without_mask": people_without_mask,
        "people_total": people_with_mask + people_without_mask,
    }

    statistic = create_statistic(
        db_session=database_session, statistic_information=stat_info
    )

    assert statistic.device_id == DEVICE_ID
    assert statistic.datetime == now.replace(tzinfo=None)
    assert statistic.statistic_type == StatisticTypeEnum.ALERT
    assert statistic.people_with_mask == people_with_mask
    assert statistic.people_without_mask == people_without_mask
    assert statistic.people_total == people_with_mask + people_without_mask


def test_create_same_statistic():
    people_with_mask = 4
    people_without_mask = 7
    # now = datetime(2021, 1, 4, 17, 22, 51, 514455, tzinfo=timezone.utc)
    now = convert_timestamp_to_datetime(1609780971.514455)

    with pytest.raises(IntegrityError):
        stat_info = {
            "device_id": DEVICE_ID,
            "datetime": now,
            "statistic_type": StatisticTypeEnum.ALERT,
            "people_with_mask": people_with_mask,
            "people_without_mask": people_without_mask,
            "people_total": people_with_mask + people_without_mask,
        }

        create_statistic(
            db_session=database_session, statistic_information=stat_info
        )


def test_create_another_statistic():
    people_with_mask = 5
    people_without_mask = 8
    # now = datetime(2021, 1, 5, 17, 22, 51, 514455, tzinfo=timezone.utc)
    now = convert_timestamp_to_datetime(1609867371.514455)

    stat_info = {
        "device_id": DEVICE_ID,
        "datetime": now,
        "statistic_type": StatisticTypeEnum.ALERT,
        "people_with_mask": people_with_mask,
        "people_without_mask": people_without_mask,
        "people_total": people_with_mask + people_without_mask,
    }

    statistic = create_statistic(
        db_session=database_session, statistic_information=stat_info
    )

    assert statistic.device_id == DEVICE_ID
    assert statistic.datetime == now.replace(tzinfo=None)
    assert statistic.statistic_type == StatisticTypeEnum.ALERT
    assert statistic.people_with_mask == people_with_mask
    assert statistic.people_without_mask == people_without_mask
    assert statistic.people_total == people_with_mask + people_without_mask


def test_get_statistic():
    people_with_mask = 4
    people_without_mask = 7
    # now = datetime(2021, 1, 4, 17, 22, 51, 514455, tzinfo=timezone.utc)
    now = convert_timestamp_to_datetime(1609780971.514455)

    statistic = get_statistic(
        db_session=database_session, device_id=DEVICE_ID, datetime=now
    )

    assert statistic.device_id == DEVICE_ID
    assert statistic.datetime == now.replace(tzinfo=None)
    assert statistic.statistic_type == StatisticTypeEnum.ALERT
    assert statistic.people_with_mask == people_with_mask
    assert statistic.people_without_mask == people_without_mask
    assert statistic.people_total == people_with_mask + people_without_mask


def test_update_statistic():
    people_without_mask = 7
    # now = datetime(2021, 1, 4, 17, 22, 51, 514455, tzinfo=timezone.utc)
    now = convert_timestamp_to_datetime(1609780971.514455)

    statistic = update_statistic(
        db_session=database_session,
        device_id=DEVICE_ID,
        datetime=now,
        new_statistic_information={"people_with_mask": 20, "people_total": 27},
    )

    assert statistic.device_id == DEVICE_ID
    assert statistic.datetime == now.replace(tzinfo=None)
    assert statistic.statistic_type == StatisticTypeEnum.ALERT
    assert statistic.people_with_mask == 20
    assert statistic.people_without_mask == people_without_mask
    assert statistic.people_total == 27


def test_delete_statistic():
    people_with_mask = 20
    people_without_mask = 7
    # now = datetime(2021, 1, 4, 17, 22, 51, 514455, tzinfo=timezone.utc)
    now = convert_timestamp_to_datetime(1609780971.514455)

    statistic = delete_statistic(
        db_session=database_session,
        device_id=DEVICE_ID,
        datetime=now,
    )

    assert statistic.device_id == DEVICE_ID
    assert statistic.datetime == now.replace(tzinfo=None)
    assert statistic.statistic_type == StatisticTypeEnum.ALERT
    assert statistic.people_with_mask == people_with_mask
    assert statistic.people_without_mask == people_without_mask
    assert statistic.people_total == people_with_mask + people_without_mask


def test_delete_device():
    device = delete_device(db_session=database_session, device_id=DEVICE_ID)

    assert device.id == DEVICE_ID
    assert device.description == "new description"


def test_get_deleted_device():
    with pytest.raises(NoResultFound):
        get_device(db_session=database_session, device_id=DEVICE_ID)


def test_update_deleted_device():
    with pytest.raises(NoResultFound):
        update_device(
            db_session=database_session,
            device_id=DEVICE_ID,
            new_device_information={"description": "new test description"},
        )


def test_get_devices():
    devices = get_devices(db_session=database_session)

    assert devices == []


def test_get_devices():
    stats = get_statistics(db_session=database_session)

    assert stats == []


database_session.close()

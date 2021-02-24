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

from app.db.schema import VideoFilesModel

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound


def update_files(
    db_session: Session,
    device_id: str,
    file_list: List,
) -> List[VideoFilesModel]:
    """
    Update the whole list of available files for this device

    Arguments:
        db_session {Session} -- Database session.
        device_id {str} -- Jetson id which sent the information.
        file_list {List} -- List of all available files in the device

    Returns:
        VideoFilesModel -- Updated video_files instance defined by device_id
    """
    # Remove all previous files for device_id
    query = db_session.query(VideoFilesModel)
    query = query.filter(VideoFilesModel.device_id == device_id)
    query.delete(synchronize_session=False)
    db_session.commit()

    # Add new list
    result = []
    for new_file in file_list:
        file_add = VideoFilesModel(device_id=device_id, video_name=new_file)
        db_session.add(file_add)
        result.append(file_add)

    db_session.commit()
    return result


def get_files_by_device(
    db_session: Session, device_id: str
) -> List[VideoFilesModel]:
    """
    Get a file using the table's primary keys.

    Arguments:
        db_session {Session} -- Database session.
        device_id {str} -- Jetson id to query files

    Returns:
        List[VideoFilesModel] -- All video files for the device
    """
    query = db_session.query(VideoFilesModel)
    return query.filter(VideoFilesModel.device_id == device_id).all()

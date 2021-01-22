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
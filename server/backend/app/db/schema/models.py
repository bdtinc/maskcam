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

from app.db.schema import Base
from app.db.utils import StatisticTypeEnum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship


class StatisticsModel(Base):
    __tablename__ = "statistic"

    device_id = Column(
        String,
        ForeignKey("device.id"),
        primary_key=True,
    )
    datetime = Column(DateTime(timezone=True), primary_key=True)
    statistic_type = Column(Enum(StatisticTypeEnum, nullable=False))
    people_with_mask = Column(Integer, nullable=False)
    people_without_mask = Column(Integer, nullable=False)
    people_total = Column(Integer, nullable=False)


class VideoFilesModel(Base):
    __tablename__ = "video_file"
    device_id = Column(
        String,
        ForeignKey("device.id"),
        primary_key=True,
    )
    video_name = Column(String, primary_key=True)
 

class DeviceModel(Base):
    __tablename__ = "device"

    id = Column(String, primary_key=True)
    description = Column(String)
    file_server_address = Column(String)
    statistics = relationship("StatisticsModel", cascade="all, delete")
    video_files = relationship("VideoFilesModel", cascade="all, delete")

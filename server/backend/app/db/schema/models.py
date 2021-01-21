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
    statistics = relationship("StatisticsModel", cascade="all, delete")
    video_files = relationship("VideoFilesModel", cascade="all, delete")

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Schedule(Base):
    __tablename__ = "schedule"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    frequency_type = Column(String)
    interval_value = Column(Integer)
    active = Column(Boolean, default=True)
    max_retries = Column(Integer, default=3)
    next_run_time = Column(DateTime(timezone=True))
    last_run_time = Column(DateTime(timezone=True))

    items = relationship("Item", back_populates="schedule")

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    item_code = Column(String)
    name = Column(String)
    url = Column(String)
    schedule_id = Column(Integer, ForeignKey("schedule.id"))
    last_run_time = Column(DateTime(timezone=True))
    status = Column(String)
    active = Column(Boolean, default=True)

    schedule = relationship("Schedule", back_populates="items")

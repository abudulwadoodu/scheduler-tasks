from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Float, Text
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone

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
    rrule = Column(String, nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=True)
    timezone = Column(String, default='UTC')

    items = relationship("Item", back_populates="schedule")
    sources = relationship("Source", back_populates="schedule")

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

    # New Columns
    source_id = Column(Integer, ForeignKey("sources.source_id"), nullable=True)
    rate = Column(Float, nullable=True)
    last_price_updated_at = Column(DateTime(timezone=True), nullable=True)
    remarks = Column(Text, nullable=True)
    no_of_revisions = Column(Integer, default=0)
    prompt_details = Column(Text, nullable=True)
    comments = Column(Text, nullable=True)
    script_id = Column(Integer, ForeignKey("scripts.id"), nullable=True)
    instant_flag = Column(Boolean, default=False)
    item_type = Column(String, nullable=True)

    source = relationship("Source", back_populates="items")
    script = relationship("Script", back_populates="items")

class Source(Base):
    __tablename__ = "sources"
    source_id = Column(Integer, primary_key=True)
    source_name = Column(String)
    source_type = Column(String)
    base_url = Column(String)
    login_required = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    last_crawled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    schedule_id = Column(Integer, ForeignKey("schedule.id"), nullable=True)

    schedule = relationship("Schedule", back_populates="sources")
    scripts = relationship("Script", back_populates="source")
    items = relationship("Item", back_populates="source")

class Script(Base):
    __tablename__ = "scripts"
    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.source_id"))
    type = Column(String)
    path = Column(String)

    source = relationship("Source", back_populates="scripts")
    items = relationship("Item", back_populates="script")

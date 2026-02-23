from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Float, Text, BigInteger
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.types import UserDefinedType
from datetime import datetime, timezone


class VECTOR(UserDefinedType):
    """
    Custom SQLAlchemy type for SQL Server 2025 VECTOR(n) columns.
    SQLAlchemy has no built-in support for this type, so we define it here
    so that create_all() emits the correct DDL: VECTOR(dimensions).
    """
    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def get_col_spec(self, **kw):
        return f"VECTOR({self.dimensions})"

    cache_ok = True

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
    description = Column(Text, nullable=True)
    remarks = Column(Text, nullable=True)
    no_of_revisions = Column(Integer, default=0)
    expression = Column(Text, nullable=True)
    comments = Column(Text, nullable=True)
    script_id = Column(Integer, ForeignKey("scripts.id"), nullable=True)
    instant_flag = Column(Boolean, default=False)
    item_type = Column(String, nullable=True)

    source = relationship("Source", back_populates="items")
    script = relationship("Script", back_populates="items")
    embeddings = relationship("ItemEmbedding", back_populates="item", cascade="all, delete-orphan")

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

class JobSummary(Base):
    __tablename__ = "job_summary"
    id = Column(Integer, primary_key=True)
    job_id = Column(BigInteger, index=True)
    start_time = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    num_of_items = Column(Integer, default=0)

class ItemHistory(Base):
    __tablename__ = "item_history"
    id = Column(Integer, primary_key=True)
    job_id = Column(BigInteger, index=True)
    schedule_id = Column(Integer, ForeignKey("schedule.id"))
    item_id = Column(Integer, ForeignKey("items.id"))
    item_price = Column(Float, nullable=True)
    status = Column(String)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    schedule = relationship("Schedule")
    item = relationship("Item")


class ItemEmbedding(Base):
    """
    Stores vector embeddings for items, enabling semantic similarity search
    via SQL Server 2025's native VECTOR type and VECTOR_DISTANCE function.

    Moved here from migration_vector_search.sql so that init_db.py can create
    this table alongside all other tables in a single step.
    """
    __tablename__ = "item_embeddings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=True)
    content = Column(Text, nullable=True)
    embedding = Column(VECTOR(384), nullable=False)  # dimensions match all-MiniLM-L6-v2
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    item = relationship("Item", back_populates="embeddings")

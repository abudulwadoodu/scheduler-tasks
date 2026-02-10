from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from scheduler_core.config import Config

engine = create_engine(Config.DB_URL)
SessionLocal = sessionmaker(bind=engine)

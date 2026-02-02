import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from app.models import Base
from app.db import engine
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv("DB_URL"))
Base.metadata.create_all(bind=engine)

print("DB created")

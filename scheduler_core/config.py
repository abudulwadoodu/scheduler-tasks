import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def get_project_root():
    return Path(__file__).resolve().parents[1]

def load_yml_config():
    project_root = get_project_root()
    config_path = project_root / "config" / "config.yml"
    
    if not config_path.exists():
        return {}

    with open(config_path, "r") as f:
        return yaml.safe_load(f)

class Config:
    YML = load_yml_config()
    
    # Database
    DB_URL = os.getenv("DB_URL") or YML.get("database", {}).get("url") or "sqlite:///scheduler.db"
    
    # Redis
    REDIS_HOST = os.getenv("REDIS_HOST") or YML.get("redis", {}).get("host") or "localhost"
    REDIS_PORT = int(os.getenv("REDIS_PORT") or YML.get("redis", {}).get("port") or 6379)
    
    # Scheduler
    BATCH_SIZE = int(os.getenv("BATCH_SIZE") or 10)
    INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS") or 30)

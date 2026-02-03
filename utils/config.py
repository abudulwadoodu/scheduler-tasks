from pathlib import Path
import yaml

def load_config():
    # project_root = parent of utils/
    project_root = Path(__file__).resolve().parents[1]
    config_path = project_root / "config" / "config.yml"

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r") as f:
        return yaml.safe_load(f)

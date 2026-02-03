import subprocess
import yaml
import os
import sys

from utils.config import load_config

cfg = load_config()


replicas = cfg["pipeline"]["extractor"]["replicas"]
prefix = cfg["pipeline"]["extractor"]["stream_prefix"]

PYTHON = sys.executable  # 🔑 THIS IS THE KEY

for i in range(replicas):
    env = os.environ.copy()
    env["STREAM_NAME"] = f"{prefix}{i+1}"
    env["CONSUMER_NAME"] = f"ext{i+1}"

    subprocess.Popen(
        [PYTHON, "-m", "extractor.worker"],  # 👈 IMPORTANT
        env=env
    )

print(f"[launcher] Started {replicas} extractors")

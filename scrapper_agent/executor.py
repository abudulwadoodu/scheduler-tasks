"""
scraper_agent/executor.py
=========================
Writes a generated script to a temp file and runs it in a subprocess,
passing the target URL as a command-line argument.
Returns (stdout, stderr, returncode).
"""

import sys
import subprocess
import tempfile
from pathlib import Path

from .config import SCRIPT_TIMEOUT

SCRIPTS_DIR = Path(__file__).parent / "scripts"


def execute_script(script_code: str, url: str) -> tuple[str, str, int]:
    """
    Write *script_code* to a temporary .py file and execute it with *url*
    as sys.argv[1].

    Returns:
        (stdout, stderr, returncode)

    Raises:
        subprocess.TimeoutExpired — if the script exceeds SCRIPT_TIMEOUT seconds.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(script_code)
        script_path = f.name

    print(f"[executor] Running script: {script_path}")

    result = subprocess.run(
        [sys.executable, script_path, url],
        capture_output=True,
        text=True,
        timeout=SCRIPT_TIMEOUT,
    )

    return result.stdout, result.stderr, result.returncode


def save_script(script_code: str, filename: str) -> Path:
    """
    Save *script_code* to SCRIPTS_DIR/<filename>.
    Creates the scripts directory if it does not exist.
    Returns the full path of the saved file.
    """
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    dest = SCRIPTS_DIR / filename
    dest.write_text(script_code, encoding="utf-8")
    print(f"[executor] Script saved: {dest}")
    return dest
"""
scraper_agent/agent.py
======================
Public interface for the scraper agent.

Other agents in the workflow import and call run_agent() from this module only.
All internal implementation details (generator, executor, validator) are private
to this package.

Workflow:
    generate → execute → validate
                ↑                ↓ (on failure, up to MAX_RETRIES times)
              fix ←———————— error context
"""

import subprocess
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent.parent / ".env")

from .config import MAX_RETRIES, SCRIPT_TIMEOUT, STEPS, PRICE_XPATH
from .generator import generate_script, fix_script
from .executor import execute_script, save_script
from .validator import validate_result, build_error_context


def run_agent(
    url: str,
    steps: list[dict] = STEPS,
    price_xpath: str = PRICE_XPATH,
) -> str:
    """
    Run the full scraper agent workflow for the given *url*.

    Args:
        url:         Product page URL to scrape.
        steps:       Interaction steps (defaults to config.STEPS).
        price_xpath: XPath for the price element (defaults to config.PRICE_XPATH).

    Returns:
        The extracted price string on success (e.g. "24.99").
        The last error message string on failure after all retries are exhausted.
    """
    client = OpenAI()

    script: str | None = None
    last_error: str = "Unknown error"

    for attempt in range(MAX_RETRIES + 1):  # attempt 0 = first generation
        is_first = attempt == 0

        # --- Generate / Regenerate ---
        if is_first:
            script = generate_script(client, steps, price_xpath)
        else:
            print(f"[agent] Attempt {attempt + 1}/{MAX_RETRIES + 1}...")
            script = fix_script(client, steps, price_xpath, script, last_error)

        # --- Execute ---
        try:
            stdout, stderr, returncode = execute_script(script, url)
        except subprocess.TimeoutExpired:
            last_error = f"Script timed out after {SCRIPT_TIMEOUT}s"
            print(f"[agent] {last_error}")
            continue

        combined = stdout + ("\n" + stderr if stderr.strip() else "")
        print(f"[agent] Output:\n{combined.strip()}\n")

        # --- Validate ---
        price = validate_result(stdout)
        if price:
            print(f"[agent] Success — price: {price}")
            save_script(script, f"scrape_attempt_{attempt + 1}.py")
            return price

        # --- Build error context for next fix ---
        last_error = build_error_context(stdout, stderr, returncode)
        print(f"[agent] Attempt {attempt + 1} failed: {last_error[:200]}")

    print(f"[agent] All attempts exhausted. Returning last error.")
    return last_error


# ---------------------------------------------------------------------------
# Entry point — for running this agent standalone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    url = input("Enter URL: ").strip()
    result = run_agent(url=url)
    print(f"\nResult: {result}")
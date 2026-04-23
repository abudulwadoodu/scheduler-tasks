"""
scraper_agent/generator.py
==========================
Handles all OpenAI API interactions for this agent:
  - generate_script(): first-pass generation from the base prompt
  - fix_script():      regeneration given a failing script + its error output
"""

import re
import json
import textwrap

from openai import OpenAI

from .config import MODEL
from .prompt import BASE_PROMPT


def _strip_fences(code: str) -> str:
    """Remove accidental markdown fences the model may add despite instructions."""
    code = code.strip()
    if code.startswith("```"):
        code = re.sub(r"^```[a-z]*\n?", "", code)
        code = re.sub(r"\n?```$", "", code)
    return code.strip()


def _call(client: OpenAI, prompt: str) -> str:
    """Send a single-turn prompt to the OpenAI chat completions API."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return _strip_fences(response.choices[0].message.content)


def generate_script(
    client: OpenAI,
    steps: list[dict],
    price_xpath: str,
) -> str:
    """
    Ask the model to generate a fresh scrape_price.py from scratch.
    Returns the raw Python source code as a string.
    """
    print("[generator] Generating script...")

    prompt = BASE_PROMPT

    return _call(client, prompt)


def fix_script(
    client: OpenAI,
    steps: list[dict],
    price_xpath: str,
    previous_script: str,
    error: str,
) -> str:
    """
    Ask the model to fix a failing script, given the script and its error output.
    Returns the corrected raw Python source code as a string.
    """
    print("[generator] Regenerating script with error context...")

    requirements = BASE_PROMPT.format(
        steps_json=json.dumps(steps, indent=4),
        price_xpath_json=json.dumps(price_xpath),
    )

    prompt = textwrap.dedent(f"""
        The script below failed to extract a price. Fix it.

        ## Error output
        {error.strip()}

        ## Requirements (unchanged)
        {requirements}

        ## Failing script
        ```python
        {previous_script}
        ```

        Return ONLY the corrected raw Python source code. No markdown fences,
        no explanation, no preamble.
    """).strip()

    return _call(client, prompt)
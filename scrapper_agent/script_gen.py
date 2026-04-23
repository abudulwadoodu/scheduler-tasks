"""
Agno agent that reads prompt.md, injects steps + price_xpath,
and generates a ready-to-run Playwright scraping script.
"""

import json
from dotenv import load_dotenv
load_dotenv()
import os
import re
from pathlib import Path

from agno.agent import Agent
from agno.models.openai import OpenAIChat


# ------------------------------------------------------------------ #
# Prompt loader                                                        #
# ------------------------------------------------------------------ #

def load_prompt(steps: list[dict], price_xpath: str, prompt_file: str = "prompt.md") -> str:
    """Read prompt.md and replace {steps} and {price_xpath} placeholders."""
    template = Path(prompt_file).read_text(encoding="utf-8")
    prompt = template.replace("{steps}", json.dumps(steps, indent=2))
    prompt = prompt.replace("{price_xpath}", price_xpath)
    return prompt


# ------------------------------------------------------------------ #
# Code extractor                                                       #
# ------------------------------------------------------------------ #

def extract_code(response: str) -> str:
    """
    Pull the Python code block out of the agent's markdown response.
    Falls back to the raw response if no fenced block is found.
    """
    match = re.search(r"```python\s*(.*?)```", response, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Try generic fenced block
    match = re.search(r"```\s*(.*?)```", response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return response.strip()


# ------------------------------------------------------------------ #
# Agent factory                                                        #
# ------------------------------------------------------------------ #

def build_agent() -> Agent:
    return Agent(
        name="ScriptGeneratorAgent",
        model=OpenAIChat(id="gpt-5.2", temperature=0.2),
        description=(
            "You are an expert Python developer specialising in Playwright web scraping. "
            "When given a specification, you output ONLY a complete, runnable Python script "
            "inside a single ```python ... ``` code block. "
            "No explanations, no extra text outside the code block."
        ),
        markdown=False,
    )


# ------------------------------------------------------------------ #
# Main generator function                                             #
# ------------------------------------------------------------------ #

def generate_script(
    steps: list[dict],
    price_xpath: str,
    prompt_file: str = "prompt.md",
    output_file: str = "scrape_price.py",
) -> str:
    """
    Load the prompt, run the agent, extract the code, and save to output_file.

    Returns the generated script as a string.
    """
    print(f"[INFO] Loading prompt from '{prompt_file}'...")
    prompt = load_prompt(steps, price_xpath, prompt_file)

    print("[INFO] Running agent...")
    agent = build_agent()
    response = agent.run(prompt)

    # agno returns a RunResponse object; grab the text content
    raw = response.content if hasattr(response, "content") else str(response)

    print("[INFO] Extracting code...")
    script = extract_code(raw)

    Path(output_file).write_text(script, encoding="utf-8")
    print(f"[INFO] Script saved to '{output_file}'")

    return script


# ------------------------------------------------------------------ #
# Entry point                                                          #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    # ---------- configure your inputs here ----------
    STEPS = [
        {"action": "select_dropdown", "xpath": "//*[@id='attribute188']", "value": "15"},
        {"action": "select_dropdown", "xpath": "//*[@id='attribute187']", "value": "25"},
    ]

    PRICE_XPATH = (
        "//div[contains(@class,'final-price-excl-tax')]"
        "//span[contains(@class,'price text-base')]"
    )
    # ------------------------------------------------

    script = generate_script(
        steps=STEPS,
        price_xpath=PRICE_XPATH,
        prompt_file="prompt.md",
        output_file="scrape_price.py",
    )

    print("\n===== Generated Script Preview (first 20 lines) =====")
    for line in script.splitlines()[:20]:
        print(line)
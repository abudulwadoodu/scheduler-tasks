"""
scraper_agent/config.py
=======================
All constants and default runtime configuration for the scraper agent.
Other agents in the workflow can override these by passing arguments
directly to run_agent() rather than modifying this file.
"""

MODEL = "gpt-5.2"
MAX_RETRIES = 2       # regeneration attempts after the first failure
SCRIPT_TIMEOUT = 120  # seconds before the subprocess is force-killed

STEPS = [
    {
        "action": "select_dropdown",
        "xpath": "//*[@id='attribute188']",
        "value": "15",
    },
    {
        "action": "select_dropdown",
        "xpath": "//*[@id='attribute187']",
        "value": "25",
    },
    {
        "action": "wait",
        "value": "800",
    },
]

PRICE_XPATH = "//div[contains(@class,'final-price-excl-tax')]//span[contains(@class,'price text-base')]"

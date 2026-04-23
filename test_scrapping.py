"""
Web scraping utility using Playwright (sync API).
Supports dynamic interactions before extracting a price element.
"""

import random
import re
import time
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import expect



def _select_option_partial(page, xpath: str, target: str) -> bool:
    """
    Select the first <option> matching `target` using 3 strategies (in order):
      1. Leading number in value equals target exactly  e.g. "25" matches "25+0.65"
         Safe: uses == so "15" will NEVER match "150"
      2. Word-boundary match on visible text
         e.g. "15" matches "15mm Wall" but NOT "150mm Wall"
      3. Word-boundary match on raw value attribute
         e.g. "15" matches "pipe-15-foil" but NOT "pipe-150-foil"

    Returns True if matched and selected, False otherwise.
    """
    target_stripped = target.strip()
    target_lower    = target_stripped.lower()
    css_selector    = _xpath_to_css_for_select(xpath)
    options         = page.query_selector_all(f"{css_selector} option")

    # Pre-compile word-boundary pattern: matches target only when NOT
    # surrounded by other digits. e.g. 15 matches "15mm" but NOT "150mm".
    boundary_pattern = re.compile(
        r"(?<!\d)" + re.escape(target_stripped) + r"(?!\d)",
        re.IGNORECASE,
    )

    for option in options:
        text      = option.inner_text().strip()
        raw_value = (option.get_attribute("value") or "").strip()

        # Strategy 1 — leading number in value equals target exactly
        # "25" == leading("25+0.65") ✅   "15" == leading("150+x") ✗ (150 ≠ 15)
        leading = re.match(r"^(\d+(?:\.\d+)?)", raw_value)
        if leading and leading.group(1) == target_stripped:
            page.select_option(css_selector, value=raw_value)
            print(f"[INFO] Matched '{target}' (leading number) → text='{text}' value='{raw_value}'")
            return True

        # Strategy 2 — word-boundary match on visible text
        # "15" matches "15mm Thick" ✅  but NOT "150mm Thick" ✗
        if boundary_pattern.search(text):
            page.select_option(css_selector, value=raw_value)
            print(f"[INFO] Matched '{target}' (text word-boundary) → text='{text}' value='{raw_value}'")
            return True

        # Strategy 3 — word-boundary match on raw value attribute
        # "15" matches "pipe-15-foil" ✅  but NOT "pipe-150-foil" ✗
        if boundary_pattern.search(raw_value):
            page.select_option(css_selector, value=raw_value)
            print(f"[INFO] Matched '{target}' (value word-boundary) → text='{text}' value='{raw_value}'")
            return True

    # Nothing matched — print all available options to help debug
    print(f"[DEBUG] No match for '{target}' in {xpath}. Available options:")
    for option in options:
        print(f"         text='{option.inner_text().strip()}'  value='{option.get_attribute('value')}'")
    return False


def _xpath_to_css_for_select(xpath: str) -> str:
    """
    Convert simple id-based XPath like //*[@id='attribute188'] to CSS #attribute188
    so query_selector_all works cleanly. Falls back to the raw xpath string if
    the pattern doesn't match (Playwright CSS selector handles it).
    """
    match = re.match(r"^(?:\/\/\*|\/\/\w+)\[@id=['\"](.+?)['\"]\]$", xpath)
    if match:
        return f"#{match.group(1)}"
    return xpath


def scrape_price(
    url: str,
    steps: list[dict],
    price_xpath: str,
    headless: bool = True,
    screenshot_path: Optional[str] = None,
    timeout: int = 30_000,
) -> str:
    """
    Navigate to a URL, perform a sequence of interaction steps, and extract a price.

    Args:
        url:             The page URL to navigate to.
        steps:           Ordered list of interaction step dicts. Each dict must contain:
                           - "action": one of "select_dropdown" | "click" | "hover" | "fill" | "wait"
                           - "xpath":  XPath string targeting the element (not required for "wait")
                           - "value":  Value to select/fill (required for "select_dropdown" and "fill";
                                       for "wait" it is treated as milliseconds to sleep)
        price_xpath:     XPath of the element containing the final price text.
        headless:        Launch browser in headless mode when True (default).
        screenshot_path: If provided, save a screenshot to this path after extraction.
        timeout:         Milliseconds to wait for elements / navigation (default 30 000).

    Returns:
        The extracted price as a cleaned string (digits and decimal point only).

    Raises:
        ValueError:   If a step dict is missing required keys or contains an unknown action.
        RuntimeError: If a step interaction fails.
        TimeoutError: If the price element cannot be located within *timeout* ms.
    """
    playwright_instance = sync_playwright().start()
    browser = playwright_instance.chromium.launch(headless=headless)

    try:
        page = browser.new_page()

        # ------------------------------------------------------------------ #
        # Navigation                                                           #
        # ------------------------------------------------------------------ #
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        except PlaywrightTimeoutError:
            page.goto(url, wait_until="load", timeout=timeout)

        # Give JS frameworks (Alpine.js, Vue, React, etc.) time to hydrate.
        time.sleep(2)

        # ------------------------------------------------------------------ #
        # Interaction steps                                                    #
        # ------------------------------------------------------------------ #
        for index, step in enumerate(steps, start=1):
            action = step.get("action")
            xpath  = step.get("xpath")
            value  = step.get("value")

            if not action:
                raise ValueError(f"Step {index} is missing the required 'action' key: {step}")

            try:
                if action == "wait":
                    wait_ms = int(value) if value is not None else 1_000
                    time.sleep(wait_ms / 1_000)

                elif action == "click":
                    if not xpath:
                        raise ValueError(f"Step {index} ('click') is missing the 'xpath' key.")
                    locator = page.locator(f"xpath={xpath}")
                    locator.wait_for(state="visible", timeout=timeout)
                    locator.click()

                elif action == "hover":
                    if not xpath:
                        raise ValueError(f"Step {index} ('hover') is missing the 'xpath' key.")
                    locator = page.locator(f"xpath={xpath}")
                    locator.wait_for(state="visible", timeout=timeout)
                    locator.hover()

                elif action == "fill":
                    if not xpath:
                        raise ValueError(f"Step {index} ('fill') is missing the 'xpath' key.")
                    if value is None:
                        raise ValueError(f"Step {index} ('fill') is missing the 'value' key.")
                    locator = page.locator(f"xpath={xpath}")
                    locator.wait_for(state="visible", timeout=timeout)
                    locator.fill(str(value))

                elif action == "select_dropdown":
                    if not xpath:
                        raise ValueError(f"Step {index} ('select_dropdown') is missing the 'xpath' key.")
                    if value is None:
                        raise ValueError(f"Step {index} ('select_dropdown') is missing the 'value' key.")

                    # Wait for the element to be visible first
                    locator = page.locator(f"xpath={xpath}")
                    locator.wait_for(state="visible", timeout=timeout)

                    # Use partial match — handles "25+0.65", "25mm", etc.
                    matched = _select_option_partial(page, xpath, str(value))
                    if not matched:
                        raise RuntimeError(
                            f"Step {index} ('select_dropdown'): no option matching "
                            f"'{value}' found in {xpath}"
                        )

                else:
                    raise ValueError(
                        f"Step {index} contains unknown action '{action}'. "
                        "Valid actions: select_dropdown, click, hover, fill, wait."
                    )

            except (ValueError, RuntimeError):
                raise
            except PlaywrightTimeoutError as exc:
                raise RuntimeError(
                    f"Step {index} (action='{action}', xpath='{xpath}') timed out "
                    f"after {timeout} ms."
                ) from exc
            except Exception as exc:
                raise RuntimeError(
                    f"Step {index} (action='{action}', xpath='{xpath}') failed: {exc}"
                ) from exc

            # Small random delay between steps to mimic human behaviour.
            if action != "wait":
                time.sleep(random.uniform(0.5, 1.5))

        # ------------------------------------------------------------------ #
        # Price extraction                                                     #
        # ------------------------------------------------------------------ #
        try:
            price_locator = page.locator(f"xpath={price_xpath}")
            price_locator.wait_for(state="attached", timeout=timeout)
            expect(price_locator).not_to_be_empty(timeout=timeout)
            raw_price = price_locator.inner_text()
            if not raw_price.strip():
                raise ValueError(f"Price element found but empty for XPath: {price_xpath}")
            
        except PlaywrightTimeoutError as exc:
            raise TimeoutError(
                f"Price element not found within {timeout} ms using XPath: {price_xpath}"
            ) from exc

        cleaned_price = raw_price.strip()
        cleaned_price = re.sub(r"[$€£¥₹,\s]", "", cleaned_price)

        print(f"Extracted price: {cleaned_price}")

        if screenshot_path:
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"Screenshot saved to: {screenshot_path}")

        return cleaned_price

    finally:
        browser.close()
        playwright_instance.stop()


if __name__ == "__main__":
    steps = [
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

    #price_path = "//div[@class='price-excl-taxinline-block']//span[@class='price']"
    price_path = "//div[contains(@class,'final-price-excl-tax')]//span[contains(@class,'price text-base')]"


    price = scrape_price(
        url="https://www.pipelagging.com/pipe-insulation/rockwool-rocklap-1m-foil-backed-pipe-insulation-lagging",
        steps=steps,
        price_xpath=price_path,
        headless=False,
        screenshot_path="price_screenshot.png",
        timeout=20_000,
    )
    print(f"Final price: {price}")




prompt = """Write a Python web scraping script using the Playwright sync API.
 
## Function Signature
 
def scrape_price(
    url: str,
    steps: list[dict],
    price_xpath: str,
    headless: bool = True,
    screenshot_path: str | None = None,
    timeout: int = 30_000,
) -> str:
 
## Parameters
 
- url: Page URL to navigate to
- steps: Ordered list of interaction step dicts (see Step Format below)
- price_xpath: XPath of the element containing the final price
- headless: Launch browser headless when True (default)
- screenshot_path: If provided, save a screenshot after extraction
- timeout: Milliseconds for all waits (default 30_000)
 
## Step Format
 
Each step dict supports:
{
    "action": "select_dropdown" | "click" | "hover" | "fill" | "wait",
    "xpath": "<xpath string>",    # not required for "wait"
    "value": "<value>"            # required for select_dropdown / fill;
                                  # for "wait" treated as milliseconds
}
 
## Browser Behaviour
 
- Launch Chromium in headless mode (toggled via headless parameter)
- Navigation strategy:
  - First attempt: wait_until="domcontentloaded" — more reliable than networkidle
    which times out on sites with continuous background requests (analytics, chat widgets)
  - Fallback on timeout: retry with wait_until="load"
  - After navigation: time.sleep(2) to allow JS frameworks (Alpine.js, Vue, React) to hydrate
- Add a random delay of 0.5–1.5s between each non-wait step to mimic human behaviour
- Wrap the entire browser lifecycle in try/finally to always close browser and stop Playwright
 
## Dropdown Selection — Partial / Fuzzy Match
 
For select_dropdown, do NOT use exact value matching (select_option(str(value))).
Instead implement a helper _select_option_partial(page, xpath, target) that tries
3 strategies in order, stopping at the first match:
 
Strategy 1 — Leading number exact match:
Extract the leading number from the option's value attribute and compare with ==.
    leading = re.match(r"^(\\d+(?:\\.\\d+)?)", raw_value)
    if leading and leading.group(1) == target_stripped: ...
This handles values like "25+0.65", "25mm", "25-standard" when target is "25".
It is safe: "15" == "15" matches, but "15" == "150" does not — no false matches.
 
Strategy 2 — Word-boundary match on visible text.
Strategy 3 — Word-boundary match on raw value attribute.
Both use a pre-compiled regex with negative digit lookarounds:
    boundary_pattern = re.compile(
        r"(?<!\\d)" + re.escape(target_stripped) + r"(?!\\d)",
        re.IGNORECASE,
    )
This ensures "15" matches "15mm Thick" and "pipe-15-foil"
but does NOT match "150mm Thick" or "pipe-150-foil".
 
Plain substring (in) must NOT be used — it causes false matches
(e.g. "15" in "150" is True).
 
If no strategy matches, print all available options with their text and value
to aid debugging, then return False.
 
Also implement a helper _xpath_to_css_for_select(xpath) that converts simple
id-based XPaths like //*[@id='attribute188'] to CSS #attribute188 so
query_selector_all works cleanly.
 
## Price Extraction
 
- Locate the price element using price_xpath
- Wait for it to be visible (wait_for(state="visible", timeout=timeout))
- Extract inner text and clean it:
  - Strip whitespace
  - Remove currency symbols ($, €, £, ¥, ₹) and commas
- Print "Extracted price: <value>"
- Return the cleaned price string
 
## Error Handling
 
- Step dict missing action key        → ValueError with step index
- Unknown action value                → ValueError listing valid actions
- Element timeout during a step       → RuntimeError with step index, action, and XPath
- select_dropdown finds no match      → RuntimeError with step index and target value
- Price element not found             → TimeoutError with the XPath used
 
Re-raise ValueError and RuntimeError unchanged. Catch PlaywrightTimeoutError
and wrap it in the appropriate exception above.
 
## Output
 
- Return the cleaned price string
- Print "Extracted price: <value>"
- If screenshot_path is provided, save full-page screenshot and print the path"""
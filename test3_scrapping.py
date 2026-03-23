import re
import time
import random
from typing import List, Dict, Optional

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
    expect,
)


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
]

PRICE_XPATH = "//span[@class='price']"


def _xpath_to_css_for_select(xpath: str) -> str:
    """
    Converts simple id-based XPath like //*[@id='attribute188']
    into CSS selector #attribute188
    """
    match = re.search(r"@id=['\"]([^'\"]+)['\"]", xpath)
    if match:
        return f"#{match.group(1)}"
    raise ValueError(f"Unsupported XPath for select conversion: {xpath}")


def _select_option_partial(page, xpath: str, target: str) -> bool:
    """
    Select dropdown option using fuzzy matching strategies.
    """
    css_selector = _xpath_to_css_for_select(xpath)
    select_el = page.query_selector(css_selector)

    if not select_el:
        raise RuntimeError(f"Dropdown not found for xpath: {xpath}")

    options = select_el.query_selector_all("option")

    target_stripped = str(target).strip()

    boundary_pattern = re.compile(
        r"(?<!\d)" + re.escape(target_stripped) + r"(?!\d)",
        re.IGNORECASE,
    )

    # Strategy 1 — leading number exact match
    for opt in options:
        raw_value = opt.get_attribute("value") or ""
        leading = re.match(r"^(\d+(?:\.\d+)?)", raw_value)

        if leading and leading.group(1) == target_stripped:
            select_el.select_option(value=raw_value)
            return True

    # Strategy 2 — word boundary match visible text
    for opt in options:
        text = (opt.inner_text() or "").strip()
        raw_value = opt.get_attribute("value") or ""

        if boundary_pattern.search(text):
            select_el.select_option(value=raw_value)
            return True

    # Strategy 3 — word boundary match raw value
    for opt in options:
        raw_value = opt.get_attribute("value") or ""

        if boundary_pattern.search(raw_value):
            select_el.select_option(value=raw_value)
            return True

    print("Available options:")
    for opt in options:
        print(
            f"text='{opt.inner_text().strip()}', value='{opt.get_attribute('value')}'"
        )

    return False


def scrape_price(
    url: str,
    steps: List[Dict],
    price_xpath: str,
    headless: bool = True,
    screenshot_path: Optional[str] = None,
    timeout: int = 30_000,
) -> str:

    playwright = sync_playwright().start()

    browser = playwright.chromium.launch(
        headless=headless,
        args=["--disable-blink-features=AutomationControlled"],
    )

    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    )

    context.route(
        "**/*",
        lambda route: route.abort()
        if route.request.resource_type in {"image", "font", "media"}
        else route.continue_(),
    )

    page = context.new_page()

    try:

        # Navigation strategy
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        except PlaywrightTimeoutError:
            page.goto(url, wait_until="load", timeout=timeout)

        time.sleep(2)

        # Read old price if exists
        old_price = None
        try:
            locator = page.locator(f"xpath={price_xpath}")
            if locator.count() > 0:
                old_price = locator.first.inner_text().strip()
        except Exception:
            old_price = None

        # Execute steps
        for idx, step in enumerate(steps):

            if "action" not in step:
                raise ValueError(f"Step {idx} missing 'action' key")

            action = step["action"]

            if action not in {"select_dropdown", "click", "hover", "fill", "wait"}:
                raise ValueError(
                    f"Step {idx} unknown action '{action}'. Valid: select_dropdown, click, hover, fill, wait"
                )

            if action == "wait":
                wait_ms = int(step.get("value", 0))
                time.sleep(wait_ms / 1000)
                continue

            xpath = step.get("xpath")
            if not xpath:
                raise ValueError(f"Step {idx} missing xpath")

            locator = page.locator(f"xpath={xpath}")

            try:

                if action == "select_dropdown":

                    target = step.get("value")
                    if target is None:
                        raise ValueError(f"Step {idx} select_dropdown missing value")

                    for attempt in range(3):
                        try:
                            ok = _select_option_partial(page, xpath, target)
                            if not ok:
                                raise RuntimeError(
                                    f"Step {idx}: dropdown value '{target}' not found"
                                )
                            break
                        except RuntimeError:
                            raise
                        except Exception:
                            if attempt == 2:
                                raise
                            time.sleep(1)

                elif action == "click":
                    locator.wait_for(state="attached", timeout=timeout)
                    locator.scroll_into_view_if_needed()
                    locator.click()

                elif action == "hover":
                    locator.wait_for(state="attached", timeout=timeout)
                    locator.hover()

                elif action == "fill":
                    value = step.get("value")
                    if value is None:
                        raise ValueError(f"Step {idx} fill missing value")

                    locator.wait_for(state="attached", timeout=timeout)
                    locator.fill(value)

            except PlaywrightTimeoutError:
                raise RuntimeError(
                    f"Step {idx} failed: action={action}, xpath={xpath}"
                )

            time.sleep(random.uniform(0.5, 1.5))

        # Wait for price change
        if old_price is not None:
            try:
                page.wait_for_function(
                    """([xpath, oldPrice]) => {
                        const el = document.evaluate(
                            xpath, document, null,
                            XPathResult.FIRST_ORDERED_NODE_TYPE, null
                        ).singleNodeValue;
                        return el && el.innerText.trim() !== oldPrice;
                    }""",
                    arg=[price_xpath, old_price],
                    timeout=timeout,
                )
            except PlaywrightTimeoutError:
                pass

        # Price extraction
        price_locator = page.locator(f"xpath={price_xpath}")

        try:
            price_locator.wait_for(state="attached", timeout=timeout)
        except PlaywrightTimeoutError:
            raise TimeoutError(f"Price element not found: {price_xpath}")

        try:
            expect(price_locator).not_to_be_empty(timeout=timeout)
        except AssertionError:
            raise TimeoutError(f"Price element empty: {price_xpath}")

        price_text = price_locator.first.inner_text().strip()

        cleaned = re.sub(r"[₹€£¥$,]", "", price_text).replace(",", "").strip()

        print(f"Extracted price: {cleaned}")

        if screenshot_path:
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"Screenshot saved to: {screenshot_path}")

        return cleaned

    finally:
        browser.close()
        playwright.stop()


if __name__ == "__main__":

    url = input("Enter URL: ")

    price = scrape_price(
        url=url,
        steps=STEPS,
        price_xpath=PRICE_XPATH,
        headless=False,
        screenshot_path="price_screenshot.png",
        timeout=20_000,
    )

    print(f"Final price: {price}")
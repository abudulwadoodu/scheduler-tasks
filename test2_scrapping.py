import re
import time
import random
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def _xpath_to_css_for_select(xpath: str) -> str:
    """Convert simple id-based XPaths like //*[@id='foo'] to CSS #foo."""
    match = re.match(r"^//{0,2}\*\[@id=['\"](.+?)['\"]\]$", xpath)
    if match:
        return f"#{match.group(1)}"
    return xpath


def _select_option_partial(page, xpath: str, target: str) -> bool:
    """Try 3 strategies to select a dropdown option by partial/fuzzy match."""
    css = _xpath_to_css_for_select(xpath)
    target_stripped = target.strip()

    # Gather all options
    options = page.query_selector_all(f"{css} option")
    if not options:
        # fallback to xpath
        options = page.query_selector_all(f"xpath={xpath} option") if css == xpath else []

    option_data = []
    for opt in options:
        raw_value = opt.get_attribute("value") or ""
        visible_text = opt.inner_text().strip()
        option_data.append((raw_value, visible_text))

    boundary_pattern = re.compile(
        r"(?<!\d)" + re.escape(target_stripped) + r"(?!\d)",
        re.IGNORECASE,
    )

    for raw_value, visible_text in option_data:
        # Strategy 1: Leading number exact match
        leading = re.match(r"^(\d+(?:\.\d+)?)", raw_value)
        if leading and leading.group(1) == target_stripped:
            page.select_option(css if css != xpath else f"xpath={xpath}", value=raw_value)
            return True

    for raw_value, visible_text in option_data:
        # Strategy 2: Word-boundary match on visible text
        if boundary_pattern.search(visible_text):
            page.select_option(css if css != xpath else f"xpath={xpath}", value=raw_value)
            return True

    for raw_value, visible_text in option_data:
        # Strategy 3: Word-boundary match on raw value attribute
        if boundary_pattern.search(raw_value):
            page.select_option(css if css != xpath else f"xpath={xpath}", value=raw_value)
            return True

    # No match — print debug info
    print(f"[DEBUG] No match for '{target_stripped}'. Available options:")
    for raw_value, visible_text in option_data:
        print(f"  text={visible_text!r}  value={raw_value!r}")
    return False


def scrape_price(
    url: str,
    steps: list[dict],
    price_xpath: str,
    headless: bool = True,
    screenshot_path: str | None = None,
    timeout: int = 30_000,
) -> str:
    valid_actions = {"select_dropdown", "click", "hover", "fill", "wait"}

    # Validate steps upfront
    for i, step in enumerate(steps):
        if "action" not in step:
            raise ValueError(f"Step {i} is missing required 'action' key: {step}")
        if step["action"] not in valid_actions:
            raise ValueError(
                f"Step {i} has unknown action '{step['action']}'. "
                f"Valid actions: {sorted(valid_actions)}"
            )

    playwright = sync_playwright().start()
    browser = None
    try:
        browser = playwright.chromium.launch(headless=headless)
        page = browser.new_page()

        # Navigation with fallback
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        except PlaywrightTimeoutError:
            print("[WARN] domcontentloaded timed out, retrying with wait_until='load'")
            page.goto(url, wait_until="load", timeout=timeout)

        # Allow JS frameworks to hydrate
        time.sleep(2)

        # Execute steps
        for i, step in enumerate(steps):
            action = step["action"]
            xpath = step.get("xpath")
            value = step.get("value")

            if action == "wait":
                wait_ms = int(value) if value else 1000
                time.sleep(wait_ms / 1000)
                continue

            # Random human-like delay between non-wait steps
            time.sleep(random.uniform(0.5, 1.5))

            try:
                if action == "click":
                    locator = page.locator(f"xpath={xpath}")
                    locator.wait_for(state="visible", timeout=timeout)
                    locator.click()

                elif action == "hover":
                    locator = page.locator(f"xpath={xpath}")
                    locator.wait_for(state="visible", timeout=timeout)
                    locator.hover()

                elif action == "fill":
                    locator = page.locator(f"xpath={xpath}")
                    locator.wait_for(state="visible", timeout=timeout)
                    locator.fill(str(value))

                elif action == "select_dropdown":
                    locator = page.locator(f"xpath={xpath}")
                    locator.wait_for(state="visible", timeout=timeout)
                    matched = _select_option_partial(page, xpath, str(value))
                    if not matched:
                        raise RuntimeError(
                            f"Step {i} (select_dropdown): no option matched '{value}' "
                            f"for element at xpath={xpath}"
                        )

            except PlaywrightTimeoutError as e:
                raise RuntimeError(
                    f"Step {i} timed out: action='{action}', xpath='{xpath}'"
                ) from e

        # Extract price
        try:
            price_locator = page.locator(f"xpath={price_xpath}")
            price_locator.wait_for(state="visible", timeout=timeout)
            raw_text = price_locator.inner_text()
        except PlaywrightTimeoutError as e:
            raise TimeoutError(
                f"Price element not found or not visible at xpath='{price_xpath}'"
            ) from e

        # Clean price
        cleaned = raw_text.strip()
        cleaned = re.sub(r"[$€£¥₹,]", "", cleaned).strip()

        print(f"Extracted price: {cleaned}")

        # Screenshot
        if screenshot_path:
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"Screenshot saved to: {screenshot_path}")

        return cleaned

    finally:
        if browser:
            browser.close()
        playwright.stop()


if __name__ == "__main__":
    example_steps = [
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

    price = scrape_price(
        url="https://www.pipelagging.com/pipe-insulation/rockwool-rocklap-1m-foil-backed-pipe-insulation-lagging",
        steps=example_steps,
        price_xpath="//div[@class='price-excl-taxinline-block']//span[@class='price']",
        headless=False,
        screenshot_path="price_screenshot.png",
        timeout=20_000,
    )
    print(f"Final price: {price}")
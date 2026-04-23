import random
import re
import time
from typing import Optional

from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
    expect,
    sync_playwright,
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
    {
        "action": "wait",
        "value": "800",
    },
]

PRICE_XPATH = "//div[contains(@class,'final-price-excl-tax')]//span[contains(@class,'price text-base')]"


def _xpath_to_css_for_select(xpath: str) -> Optional[str]:
    m = re.fullmatch(r"""\s*//\*\[@id=(?:"([^"]+)"|'([^']+)')\]\s*""", xpath)
    if not m:
        return None
    el_id = m.group(1) or m.group(2)
    if not el_id:
        return None
    return f"#{el_id}"


def _select_option_partial(page, xpath: str, target: str) -> bool:
    target_stripped = str(target).strip()
    boundary_pattern = re.compile(
        r"(?<!\d)" + re.escape(target_stripped) + r"(?!\d)",
        re.IGNORECASE,
    )

    css = _xpath_to_css_for_select(xpath)
    if css:
        select_el = page.query_selector(css)
    else:
        select_el = page.query_selector(f"xpath={xpath}")

    if not select_el:
        raise PlaywrightTimeoutError(f"Select element not found for xpath: {xpath}")

    options = select_el.query_selector_all("option")
    if not options:
        return False

    # Strategy 1 - Leading number exact match on value attribute
    for opt in options:
        raw_value = (opt.get_attribute("value") or "").strip()
        leading = re.match(r"^(\d+(?:\.\d+)?)", raw_value)
        if leading and leading.group(1) == target_stripped:
            select_el.select_option(value=raw_value)
            return True

    # Strategy 2 - Word-boundary match on visible text
    for opt in options:
        text = (opt.inner_text() or "").strip()
        if boundary_pattern.search(text):
            raw_value = (opt.get_attribute("value") or "").strip()
            if raw_value:
                select_el.select_option(value=raw_value)
            else:
                # Fallback: select by label if value is empty
                select_el.select_option(label=text)
            return True

    # Strategy 3 - Word-boundary match on raw value attribute
    for opt in options:
        raw_value = (opt.get_attribute("value") or "").strip()
        if boundary_pattern.search(raw_value):
            select_el.select_option(value=raw_value)
            return True

    print(f"No dropdown match found for target='{target_stripped}' at xpath='{xpath}'. Available options:")
    for opt in options:
        text = (opt.inner_text() or "").strip()
        raw_value = (opt.get_attribute("value") or "").strip()
        print(f"  - text='{text}' value='{raw_value}'")

    return False


def scrape_price(
    url: str,
    steps: list[dict],
    price_xpath: str,
    headless: bool = True,
    screenshot_path: str | None = None,
    timeout: int = 30_000,
) -> str:
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )

    def _human_delay():
        time.sleep(random.uniform(0.5, 1.5))

    def _read_price_text_or_none(page) -> Optional[str]:
        try:
            loc = page.locator(f"xpath={price_xpath}")
            if loc.count() == 0:
                return None
            txt = (loc.first.inner_text() or "").strip()
            return txt if txt else None
        except Exception:
            return None

    with sync_playwright() as p:
        browser = None
        context = None
        try:
            browser = p.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(user_agent=user_agent)

            context.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in {"image", "font", "media"}
                else route.continue_(),
            )

            page = context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            except PlaywrightTimeoutError:
                page.goto(url, wait_until="load", timeout=timeout)

            time.sleep(2)

            old_price = _read_price_text_or_none(page)

            valid_actions = {"select_dropdown", "click", "hover", "fill", "wait"}

            for i, step in enumerate(steps):
                if "action" not in step:
                    raise ValueError(f"Step {i} missing 'action' key")

                action = step["action"]
                if action not in valid_actions:
                    raise ValueError(
                        f"Unknown action '{action}' at step {i}. Valid actions: {sorted(valid_actions)}"
                    )

                if action == "wait":
                    try:
                        ms = int(str(step.get("value", "0")).strip())
                    except Exception:
                        ms = 0
                    time.sleep(ms / 1000.0)
                    continue

                xpath = step.get("xpath")
                if not xpath:
                    raise ValueError(f"Step {i} action '{action}' missing 'xpath'")

                try:
                    if action == "select_dropdown":
                        if "value" not in step:
                            raise ValueError(f"Step {i} action 'select_dropdown' missing 'value'")
                        target = str(step["value"])

                        last_exc = None
                        for attempt in range(3):
                            try:
                                ok = _select_option_partial(page, xpath, target)
                                if not ok:
                                    raise RuntimeError(f"Step {i} select_dropdown found no match for value '{target}'")
                                break
                            except RuntimeError:
                                raise
                            except Exception as e:
                                last_exc = e
                                time.sleep(1.0)
                        else:
                            raise last_exc  # type: ignore[misc]

                        _human_delay()

                    elif action == "click":
                        loc = page.locator(f"xpath={xpath}")
                        loc.first.wait_for(state="attached", timeout=timeout)
                        loc.first.scroll_into_view_if_needed()
                        loc.first.click(timeout=timeout)
                        _human_delay()

                    elif action == "hover":
                        loc = page.locator(f"xpath={xpath}")
                        loc.first.wait_for(state="attached", timeout=timeout)
                        loc.first.hover(timeout=timeout)
                        _human_delay()

                    elif action == "fill":
                        if "value" not in step:
                            raise ValueError(f"Step {i} action 'fill' missing 'value'")
                        val = str(step["value"])
                        loc = page.locator(f"xpath={xpath}")
                        loc.first.wait_for(state="attached", timeout=timeout)
                        loc.first.fill(val, timeout=timeout)
                        _human_delay()

                except PlaywrightTimeoutError as e:
                    raise RuntimeError(f"Step {i} timeout during action '{action}' at XPath: {xpath}") from e

            if old_price is not None:
                try:
                    page.wait_for_function(
                        """([xpath, oldPrice]) => {
                            const el = document.evaluate(
                                xpath, document, null,
                                XPathResult.FIRST_ORDERED_NODE_TYPE, null
                            ).singleNodeValue;
                            return el && el.innerText && el.innerText.trim() !== oldPrice;
                        }""",
                        arg=[price_xpath, old_price],
                        timeout=timeout,
                    )
                except PlaywrightTimeoutError:
                    pass

            price_locator = page.locator(f"xpath={price_xpath}").first
            try:
                price_locator.wait_for(state="attached", timeout=timeout)
            except PlaywrightTimeoutError as e:
                raise TimeoutError(f"Price element not found (attached) for XPath: {price_xpath}") from e

            try:
                expect(price_locator).not_to_be_empty(timeout=timeout)
            except (PlaywrightTimeoutError, AssertionError) as e:
                raise TimeoutError(f"Price element found but empty for XPath: {price_xpath}") from e

            raw_price = (price_locator.inner_text() or "").strip()
            cleaned = re.sub(r"[€£¥₹$]", "", raw_price)
            cleaned = cleaned.replace(",", "").strip()

            print(f"Extracted price: {cleaned}")

            if screenshot_path:
                page.screenshot(path=screenshot_path, full_page=True)
                print(f"Saved screenshot: {screenshot_path}")

            return cleaned

        finally:
            if context is not None:
                try:
                    context.close()
                except Exception:
                    pass
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass


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
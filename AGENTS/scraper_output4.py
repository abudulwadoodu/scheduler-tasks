import re
import time
import random
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, expect
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import Literal, Optional
import dotenv


dotenv.load_dotenv()


SYSTEM_PROMPT = """
You are a form-filling assistant.

You will be given:
1. A Pydantic model definition representing a web form
2. A customer comment describing what they want

Your job is to extract values from the comment and return ONLY a filled Pydantic object constructor call — nothing else. No explanation, no code block, no markdown.

Rules:
- Return only the Pydantic constructor call e.g. ModelName(field=value, ...)
- Only include fields that have a value extracted from the comment
- For numerical values take numerical values from the comment and convert to string (e.g. "630mm" -> "630")
- For radio button fields (Optional[bool]): set True for the matched option, or set to default value if not specified
- For radio groups: only ONE field in the group can be True
- For checkbox fields (Optional[bool]): set True if mentioned, or set to default value if not specified
- For text fields (Optional[str]): extract the value as a string
- For select/dropdown fields (Literal[...]): pick the closest matching allowed value
- If the item is mentioned but no quantity found, default to the minimum non-zero option value
- Use Python field names (not aliases) in the constructor"""


# =========================
# CONSTANTS
# =========================
PRICE_XPATH = "//div[contains(@class, 'price-box price-final_price')]"

STEPS = []

# Pydantic model


prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{comment}"),
])


# ── Fallback Parser ───────────────────────────────────────────────────────────




# =========================
# COMMENT PARSER
# =========================



# =========================
# SMART LOCATOR
# =========================
def _smart_locator(page, step, timeout=5000):
    step_xpath = step["xpath"]
    step_label = step["label"]

    base = page.locator("xpath=" + step_xpath)

    try:
        base.wait_for(state="attached", timeout=2000)
    except Exception:
        return None

    if base.is_visible():
        return base

    element_id = base.get_attribute("id")

    if element_id:
        icon_div = page.locator(
            "label[for='" + element_id + "'] div[class*='u-check-icon']"
        )
        if icon_div.count() > 0:
            return icon_div.first

        label_for = page.locator("label[for='" + element_id + "']")
        if label_for.count() > 0:
            return label_for.first

    ancestor_label = page.locator(
        "xpath=" + step_xpath + "/ancestor::label"
    )
    if ancestor_label.count() > 0:
        ancestor_icon = ancestor_label.first.locator("div[class*='u-check-icon']")
        if ancestor_icon.count() > 0:
            return ancestor_icon.first
        return ancestor_label.first

    text = step_label.lower()
    label_by_text = page.locator(
        "//label[contains("
        "translate(normalize-space(.),"
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
        "'abcdefghijklmnopqrstuvwxyz'),"
        "'" + text + "'"
        ")]"
    )
    if label_by_text.count() > 0:
        icon = label_by_text.first.locator("div[class*='u-check-icon']")
        if icon.count() > 0:
            return icon.first
        return label_by_text.first

    wrapper = page.locator(
        "xpath=" + step_xpath + "/ancestor::*[self::div or self::span][1]"
    )
    if wrapper.count() > 0:
        return wrapper.first

    return base


# =========================
# DROPDOWN SELECT
# =========================
def _xpath_to_css_for_select(xpath: str) -> str:
    m = re.search(r"\[@id='([^']+)'\]", xpath)
    return "#" + m.group(1) if m else xpath


def _select_option_partial(page, xpath: str, target, step_index: int) -> bool:
    css = _xpath_to_css_for_select(xpath)
    target_stripped = str(target).strip()

    boundary_pattern = re.compile(
        r"(?<!\d)" + re.escape(target_stripped) + r"(?!\d)",
        re.IGNORECASE,
    )

    for attempt in range(3):
        try:
            options = page.query_selector_all(css + " option")
            if not options:
                raise RuntimeError(
                    "Step " + str(step_index) + ": no <option> elements found in select " + xpath
                )

            for opt in options:
                raw_value    = (opt.get_attribute("value") or "").strip()
                visible_text = (opt.inner_text() or "").strip()

                leading = re.match(r"^(\d+(?:\.\d+)?)", raw_value)
                if leading and leading.group(1) == target_stripped:
                    page.select_option(css, value=raw_value)
                    return True

                if boundary_pattern.search(visible_text):
                    page.select_option(css, value=raw_value)
                    return True

                if boundary_pattern.search(raw_value):
                    page.select_option(css, value=raw_value)
                    return True

            print("[DEBUG] Step " + str(step_index) + ": no option matched '" + target_stripped + "'")
            for opt in options:
                print("  text=" + repr(opt.inner_text()) + "  value=" + repr(opt.get_attribute("value")))
            raise RuntimeError(
                "Step " + str(step_index) + ": no option matching '" + target_stripped + "' found in " + xpath
            )

        except RuntimeError:
            raise
        except Exception as exc:
            if attempt == 2:
                raise RuntimeError(
                    "Step " + str(step_index) + ": select failed after 3 attempts - " + str(exc)
                ) from exc
            time.sleep(1)

    return False


def _random_delay():
    time.sleep(random.uniform(0.5, 1.5))


# =========================
# MAIN SCRAPE FUNCTION
# =========================
def scrape_price(
    url: str,
    comment: str,
    price_xpath: str,
    headless: bool = True,
    screenshot_path: str | None = None,
    timeout: int = 30_000,
) -> str:

    
   
    values = {}
    print("values : ", values)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )

        context.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in {"image", "font", "media"}
            else route.continue_(),
        )

        page = context.new_page()

        try:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            except PlaywrightTimeoutError:
                page.goto(url, wait_until="load", timeout=timeout)

            time.sleep(2)

            # Capture baseline price
            old_price: str | None = None
            try:
                price_el = page.locator("xpath=" + price_xpath)
                price_el.wait_for(state="attached", timeout=3000)
                old_price = price_el.inner_text().strip()
            except Exception:
                pass

            # =========================
            # EXECUTE STEPS
            # =========================
            for idx, step in enumerate(STEPS):
                label      = step["label"]
                step_xpath = step["xpath"]
                value      = values.get(label)

                if value is None:
                    continue

                tag   = step.get("tag", "input")
                itype = step.get("type", "")

                if tag == "select":
                    _select_option_partial(page, step_xpath, value, idx)
                    _random_delay()
                    continue

                if itype == "text":
                    locator = page.locator("xpath=" + step_xpath)
                    try:
                        locator.wait_for(state="visible", timeout=timeout)
                    except PlaywrightTimeoutError:
                        raise RuntimeError(
                            "Step " + str(idx) + ": timeout waiting for text input - " + step_xpath
                        )
                    locator.scroll_into_view_if_needed()
                    locator.click()
                    locator.type(str(value), delay=50)
                    _random_delay()
                    continue

                if value is not True:
                    continue

                smart = _smart_locator(page, step, timeout=timeout)
                if smart is None:
                    print("[WARN] Step " + str(idx) + ": could not resolve locator for '" + label + "' - skipping")
                    continue

                try:
                    smart.scroll_into_view_if_needed()
                    smart.click(timeout=timeout)
                except PlaywrightTimeoutError as exc:
                    raise RuntimeError(
                        "Step " + str(idx) + ": timeout clicking '" + itype + "' element - " + step_xpath
                    ) from exc

                _random_delay()

            # =========================
            # WAIT FOR PRICE CHANGE
            # =========================
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

            # =========================
            # EXTRACT PRICE
            # =========================
            price_locator = page.locator("xpath=" + price_xpath).first
            try:
                price_locator.wait_for(state="attached", timeout=timeout)
            except PlaywrightTimeoutError:
                raise TimeoutError("Price element not found: " + price_xpath)

            try:
                expect(price_locator).not_to_be_empty(timeout=timeout)
            except (PlaywrightTimeoutError, AssertionError):
                raise TimeoutError("Price element found but empty: " + price_xpath)

            raw_price = price_locator.inner_text().strip()
            cleaned   = re.sub(r"[€£¥₹,]", "", raw_price).strip()

            print("Extracted price: " + cleaned)

            if screenshot_path:
                page.screenshot(path=screenshot_path, full_page=True)
                print("Screenshot saved: " + screenshot_path)

            return cleaned

        finally:
            browser.close()


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    url     = input("Enter URL: ")
    comment = input("comment : ")

    price = scrape_price(
        url=url,
        comment=comment,
        price_xpath=PRICE_XPATH,
        headless=False,
        screenshot_path="price_screenshot.png",
        timeout=20_000,
    )
    print("Final price: " + price)

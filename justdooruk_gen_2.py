"""
Web scraper for extracting prices using Playwright sync API.
"""

from __future__ import annotations

import re
import time
import random

from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeoutError

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

PRICE_XPATH = '//span[contains(@class, "totalpricevisible")]'

STEPS = [
    {'label': 'Frame Width (mm)',  'xpath': "//input[@id='framewidth']",              'type': 'text',     'tag': 'input'},
    {'label': 'Frame Height (mm)', 'xpath': "//input[@id='frameheight']",             'type': 'text',     'tag': 'input'},
    {'label': 'No',                'xpath': "//input[@id='cillno']",                  'type': 'radio',    'tag': 'input'},
    {'label': '85mm Stub',         'xpath': "//input[@id='cill85']",                  'type': 'radio',    'tag': 'input'},
    {'label': 'Standard 150mm',    'xpath': "//input[@id='cill150']",                 'type': 'radio',    'tag': 'input'},
    {'label': '180mm',             'xpath': "//input[@id='cill180']",                 'type': 'radio',    'tag': 'input'},
    {'label': 'White',             'xpath': "//input[@id='White']",                   'type': 'radio',    'tag': 'input'},
    {'label': 'Oak Both Sides',    'xpath': "//input[@id='Oak Both Sides']",           'type': 'radio',    'tag': 'input'},
    {'label': 'Oak/White',         'xpath': "//input[@id='Oak/White']",               'type': 'radio',    'tag': 'input'},
    {'label': 'Rosewood Both Sides',       'xpath': "//input[@id='Rosewood Both Sides']",       'type': 'radio', 'tag': 'input'},
    {'label': 'Rosewood/White',            'xpath': "//input[@id='Rosewood/White']",            'type': 'radio', 'tag': 'input'},
    {'label': 'Anthracite Grey Both Sides','xpath': "//input[@id='Anthracite Grey Both Sides']",'type': 'radio', 'tag': 'input'},
    {'label': 'Anthracite Grey/White',     'xpath': "//input[@id='Anthracite Grey/White']",     'type': 'radio', 'tag': 'input'},
    {'label': 'Chartwell/White',           'xpath': "//input[@id='Chartwell/White']",           'type': 'radio', 'tag': 'input'},
    {'label': 'Cream Both Sides',          'xpath': "//input[@id='Cream Both Sides']",          'type': 'radio', 'tag': 'input'},
    {'label': 'Cream/White',               'xpath': "//input[@id='Cream/White']",               'type': 'radio', 'tag': 'input'},
    {'label': 'Black-Brown Both Sides',    'xpath': "//input[@id='Black-Brown Both Sides']",    'type': 'radio', 'tag': 'input'},
    {'label': 'Black-Brown/White',         'xpath': "//input[@id='Black-Brown/White']",         'type': 'radio', 'tag': 'input'},
    {'label': 'Whitegrain Both Sides',     'xpath': "//input[@id='Whitegrain Both Sides']",     'type': 'radio', 'tag': 'input'},
    {'label': 'Irish Oak Both Sides',      'xpath': "//input[@id='Irish Oak Both Sides']",      'type': 'radio', 'tag': 'input'},
    {'label': 'Smooth Anthracite Grey/White', 'xpath': "//input[@id='Smooth Anthracite Grey/White']", 'type': 'radio', 'tag': 'input'},
    {'label': 'Agate Grey/White',          'xpath': "//input[@id='Agate Grey/White']",          'type': 'radio', 'tag': 'input'},
    {'label': 'Clear',             'xpath': "//input[@id='clear']",                   'type': 'radio',    'tag': 'input'},
    {'label': 'Obscure',           'xpath': "//input[@id='obscure']",                 'type': 'radio',    'tag': 'input'},
    {'label': 'Standard A Rated',  'xpath': "//input[@id='arated']",                  'type': 'radio',    'tag': 'input'},
    {'label': 'A++ Triple Glazed', 'xpath': "//input[@id='tripleglazed']",            'type': 'radio',    'tag': 'input'},
    {'label': 'Toughened Glass',   'xpath': "//input[@id='toughened']",               'type': 'checkbox', 'tag': 'input'},
    {'label': 'Laminated Glass',   'xpath': "//input[@id='laminated']",               'type': 'checkbox', 'tag': 'input'},
    {'label': 'Trickle Vents',     'xpath': "//select[@id='tricklevents']",           'type': '',         'tag': 'select'},
    {'label': 'Fit Pack',          'xpath': "//input[@id='fitpack']",                 'type': 'checkbox', 'tag': 'input'},
]

# ---------------------------------------------------------------------------
# Comment parser
# ---------------------------------------------------------------------------

def parse_comment(comment: str, labels: list) -> dict:
    c = comment.lower()
    result = {}

    dim_match = re.search(r"(\d+)\s*[x×]\s*(\d+)", c)
    width  = dim_match.group(1) if dim_match else None
    height = dim_match.group(2) if dim_match else None

    # cill
    cill_selected = "No"
    if "standard cill" in c:
        cill_selected = "Standard 150mm"
    elif "85mm" in c:
        cill_selected = "85mm Stub"
    elif "180mm" in c:
        cill_selected = "180mm"
    elif "no cill" in c:
        cill_selected = "No"

    # colour
    colour_selected = None
    if "white upvc" in c or re.search(r"\bwhite\b", c):
        colour_selected = "White"

    colour_labels = [
        "White", "Oak Both Sides", "Oak/White",
        "Rosewood Both Sides", "Rosewood/White",
        "Anthracite Grey Both Sides", "Anthracite Grey/White",
        "Chartwell/White", "Cream Both Sides", "Cream/White",
        "Black-Brown Both Sides", "Black-Brown/White",
        "Whitegrain Both Sides", "Irish Oak Both Sides",
        "Smooth Anthracite Grey/White", "Agate Grey/White",
    ]

    # glass
    glass_selected = "Clear"
    if "obscure" in c:
        glass_selected = "Obscure"

    # energy rating
    energy_selected = "Standard A Rated"
    if "triple" in c or "a++" in c:
        energy_selected = "A++ Triple Glazed"

    # trickle vents
    trickle_value = "Not Required"
    if "trickle" in c:
        trickle_value = "2" if "2" in c else "1"

    # checkboxes
    toughened_value = "check" if "toughened" in c else None
    laminated_value = "check" if "laminated" in c else None
    fitpack_value   = "check" if "fit pack"  in c else None

    for label in labels:
        if label == "Frame Width (mm)":
            result[label] = width
        elif label == "Frame Height (mm)":
            result[label] = height
        elif label in ["No", "85mm Stub", "Standard 150mm", "180mm"]:
            result[label] = "check" if label == cill_selected else None
        elif label in colour_labels:
            result[label] = "check" if label == colour_selected else None
        elif label in ["Clear", "Obscure"]:
            result[label] = "check" if label == glass_selected else None
        elif label in ["Standard A Rated", "A++ Triple Glazed"]:
            result[label] = "check" if label == energy_selected else None
        elif label == "Toughened Glass":
            result[label] = toughened_value
        elif label == "Laminated Glass":
            result[label] = laminated_value
        elif label == "Trickle Vents":
            result[label] = trickle_value
        elif label == "Fit Pack":
            result[label] = fitpack_value
        else:
            result[label] = None

    return result

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _smart_locator(page, step, timeout=5000):
    base = page.locator(f"xpath={step['xpath']}")

    try:
        base.wait_for(state="attached", timeout=2000)
    except Exception:
        return None

    if base.is_visible():
        return base

    element_id = base.get_attribute("id")

    if element_id:
        # ✅ PRIMARY: click the u-check-icon div inside the label
        icon_div = page.locator(
            f"label[for='{element_id}'] div[class*='u-check-icon']"
        )
        if icon_div.count() > 0:
            return icon_div.first

        # Fallback: plain label[for=id]
        label_for = page.locator(f"label[for='{element_id}']")
        if label_for.count() > 0:
            return label_for.first

    # ancestor label → also try its icon div first
    ancestor_label = page.locator(
        f"xpath={step['xpath']}/ancestor::label"
    )
    if ancestor_label.count() > 0:
        ancestor_icon = ancestor_label.first.locator("div[class*='u-check-icon']")
        if ancestor_icon.count() > 0:
            return ancestor_icon.first
        return ancestor_label.first

    # label by visible text
    text = step["label"].lower()
    label_by_text = page.locator(
        f"""//label[contains(
                translate(normalize-space(.),
                'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                'abcdefghijklmnopqrstuvwxyz'),
                '{text}'
        )]"""
    )
    if label_by_text.count() > 0:
        icon = label_by_text.first.locator("div[class*='u-check-icon']")
        if icon.count() > 0:
            return icon.first
        return label_by_text.first

    # clickable wrapper fallback
    wrapper = page.locator(
        f"xpath={step['xpath']}/ancestor::*[self::div or self::span][1]"
    )
    if wrapper.count() > 0:
        return wrapper.first

    return base
    


def _xpath_to_css_for_select(xpath: str) -> str:
    """Convert //select[@id='foo'] or //*[@id='foo'] to CSS selector #foo."""
    m = re.search(r"\[@id='([^']+)'\]", xpath)
    return f"#{m.group(1)}" if m else xpath


def _select_option_partial(page, xpath: str, target, step_index: int) -> bool:
    """
    Select a <select> option using fuzzy / partial matching.
    Returns True on success, raises RuntimeError if nothing matches.
    """
    css    = _xpath_to_css_for_select(xpath)
    target_stripped = str(target).strip()

    boundary_pattern = re.compile(
        r"(?<!\d)" + re.escape(target_stripped) + r"(?!\d)",
        re.IGNORECASE,
    )

    for attempt in range(3):
        try:
            options = page.query_selector_all(f"{css} option")
            if not options:
                raise RuntimeError(
                    f"Step {step_index}: no <option> elements found in select {xpath}"
                )

            for opt in options:
                raw_value  = (opt.get_attribute("value") or "").strip()
                visible_text = (opt.inner_text() or "").strip()

                # Strategy 1 – leading number exact match
                leading = re.match(r"^(\d+(?:\.\d+)?)", raw_value)
                if leading and leading.group(1) == target_stripped:
                    page.select_option(css, value=raw_value)
                    return True

                # Strategy 2 – word-boundary match on visible text
                if boundary_pattern.search(visible_text):
                    page.select_option(css, value=raw_value)
                    return True

                # Strategy 3 – word-boundary match on raw value
                if boundary_pattern.search(raw_value):
                    page.select_option(css, value=raw_value)
                    return True

            # Debug dump
            print(f"[DEBUG] Step {step_index}: no option matched '{target_stripped}'")
            for opt in options:
                print(f"  text={opt.inner_text()!r:40s}  value={opt.get_attribute('value')!r}")
            raise RuntimeError(
                f"Step {step_index}: no option matching '{target_stripped}' found in {xpath}"
            )

        except RuntimeError:
            raise  # no point retrying a logic failure
        except Exception as exc:
            if attempt == 2:
                raise RuntimeError(
                    f"Step {step_index}: select failed after 3 attempts – {exc}"
                ) from exc
            time.sleep(1)

    return False  # unreachable


def _random_delay():
    time.sleep(random.uniform(0.5, 1.5))

# ---------------------------------------------------------------------------
# Main scraping function
# ---------------------------------------------------------------------------

def scrape_price(
    url: str,
    comment: str,
    price_xpath: str,
    headless: bool = True,
    screenshot_path: str | None = None,
    timeout: int = 30_000,
) -> str:
    """
    Navigate to *url*, fill in the configurator form described by *comment*,
    and return the extracted price string.
    """
    labels = [step["label"] for step in STEPS]
    values = parse_comment(comment, labels)

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

        # Block heavy resources for speed
        context.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in {"image", "font", "media"}
            else route.continue_(),
        )

        page = context.new_page()

        try:
            # ----------------------------------------------------------------
            # Navigation
            # ----------------------------------------------------------------
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            except PlaywrightTimeoutError:
                page.goto(url, wait_until="load", timeout=timeout)

            time.sleep(2)  # allow JS frameworks to hydrate

            # ----------------------------------------------------------------
            # Capture baseline price (for change detection later)
            # ----------------------------------------------------------------
            old_price: str | None = None
            try:
                price_el = page.locator(f"xpath={price_xpath}")
                price_el.wait_for(state="attached", timeout=3000)
                old_price = price_el.inner_text().strip()
            except Exception:
                pass  # element not yet present – that's fine

            # ----------------------------------------------------------------
            # Execute interaction steps
            # ----------------------------------------------------------------
            for idx, step in enumerate(STEPS):
                label = step["label"]
                value = values.get(label)

                if value is None:
                    continue  # nothing to do for this field

                tag  = step.get("tag", "input")
                itype = step.get("type", "")

                # ---- SELECT ----
                if tag == "select":
                    _select_option_partial(page, step["xpath"], value, idx)
                    _random_delay()
                    continue

                # ---- TEXT INPUT ----
                if itype == "text":
                    locator = page.locator(f"xpath={step['xpath']}")
                    try:
                        locator.wait_for(state="visible", timeout=timeout)
                    except PlaywrightTimeoutError:
                        raise RuntimeError(
                            f"Step {idx}: timeout waiting for text input – {step['xpath']}"
                        )
                    locator.scroll_into_view_if_needed()
                    locator.click()
                    locator.type(str(value), delay=50)
                    _random_delay()
                    continue

                # ---- RADIO / CHECKBOX ----
                if value != "check":
                    continue  # only interact when value is "check"

                smart = _smart_locator(page, step, timeout=timeout)
                if smart is None:
                    print(f"[WARN] Step {idx}: could not resolve locator for '{label}' – skipping")
                    continue

                try:
                    smart.scroll_into_view_if_needed()
                    smart.click(timeout=timeout)
                except PlaywrightTimeoutError as exc:
                    raise RuntimeError(
                        f"Step {idx}: timeout clicking '{itype}' element – {step['xpath']}"
                    ) from exc

                _random_delay()

            # ----------------------------------------------------------------
            # Wait for price to change (avoids reading a stale value)
            # ----------------------------------------------------------------
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
                    pass  # price may legitimately be unchanged

            # ----------------------------------------------------------------
            # Extract price
            # ----------------------------------------------------------------
            price_locator = page.locator(f"xpath={price_xpath}").first
            try:
                price_locator.wait_for(state="attached", timeout=timeout)
            except PlaywrightTimeoutError:
                raise TimeoutError(
                    f"Price element not found: {price_xpath}"
                )

            try:
                expect(price_locator).not_to_be_empty(timeout=timeout)
            except (PlaywrightTimeoutError, AssertionError):
                raise TimeoutError(
                    f"Price element found but empty: {price_xpath}"
                )

            raw_price = price_locator.inner_text().strip()
            cleaned   = re.sub(r"[€£¥₹,]", "", raw_price).strip()

            print(f"Extracted price: {cleaned}")

            # ----------------------------------------------------------------
            # Optional screenshot
            # ----------------------------------------------------------------
            if screenshot_path:
                page.screenshot(path=screenshot_path, full_page=True)
                print(f"Screenshot saved: {screenshot_path}")

            return cleaned

        finally:
            browser.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

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
    print(f"Final price: {price}")
"""
Playwright-based price scraper for UPVC window configurator pages.
"""

import re
import time
import random
from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeoutError

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

PRICE_XPATH = '//span[contains(@class, "totalpricevisible")]'  # override at runtime via scrape_price(price_xpath=...)

STEPS = [
    {'label': 'Frame Width (mm)',             'xpath': "//input[@id='framewidth']",                     'type': 'text',     'tag': 'input'},
    {'label': 'Frame Height (mm)',            'xpath': "//input[@id='frameheight']",                    'type': 'text',     'tag': 'input'},
    {'label': 'No',                           'xpath': "//input[@id='cillno']",                         'type': 'radio',    'tag': 'input'},
    {'label': '85mm Stub',                    'xpath': "//input[@id='cill85']",                         'type': 'radio',    'tag': 'input'},
    {'label': 'Standard 150mm',               'xpath': "//input[@id='cill150']",                        'type': 'radio',    'tag': 'input'},
    {'label': '180mm',                        'xpath': "//input[@id='cill180']",                        'type': 'radio',    'tag': 'input'},
    {'label': 'White',                        'xpath': "//input[@id='White']",                          'type': 'radio',    'tag': 'input'},
    {'label': 'Oak Both Sides',               'xpath': "//input[@id='Oak Both Sides']",                 'type': 'radio',    'tag': 'input'},
    {'label': 'Oak/White',                    'xpath': "//input[@id='Oak/White']",                      'type': 'radio',    'tag': 'input'},
    {'label': 'Rosewood Both Sides',          'xpath': "//input[@id='Rosewood Both Sides']",            'type': 'radio',    'tag': 'input'},
    {'label': 'Rosewood/White',               'xpath': "//input[@id='Rosewood/White']",                 'type': 'radio',    'tag': 'input'},
    {'label': 'Anthracite Grey Both Sides',   'xpath': "//input[@id='Anthracite Grey Both Sides']",     'type': 'radio',    'tag': 'input'},
    {'label': 'Anthracite Grey/White',        'xpath': "//input[@id='Anthracite Grey/White']",          'type': 'radio',    'tag': 'input'},
    {'label': 'Chartwell/White',              'xpath': "//input[@id='Chartwell/White']",                'type': 'radio',    'tag': 'input'},
    {'label': 'Cream Both Sides',             'xpath': "//input[@id='Cream Both Sides']",               'type': 'radio',    'tag': 'input'},
    {'label': 'Cream/White',                  'xpath': "//input[@id='Cream/White']",                    'type': 'radio',    'tag': 'input'},
    {'label': 'Black-Brown Both Sides',       'xpath': "//input[@id='Black-Brown Both Sides']",         'type': 'radio',    'tag': 'input'},
    {'label': 'Black-Brown/White',            'xpath': "//input[@id='Black-Brown/White']",              'type': 'radio',    'tag': 'input'},
    {'label': 'Whitegrain Both Sides',        'xpath': "//input[@id='Whitegrain Both Sides']",          'type': 'radio',    'tag': 'input'},
    {'label': 'Irish Oak Both Sides',         'xpath': "//input[@id='Irish Oak Both Sides']",           'type': 'radio',    'tag': 'input'},
    {'label': 'Smooth Anthracite Grey/White', 'xpath': "//input[@id='Smooth Anthracite Grey/White']",   'type': 'radio',    'tag': 'input'},
    {'label': 'Agate Grey/White',             'xpath': "//input[@id='Agate Grey/White']",               'type': 'radio',    'tag': 'input'},
    {'label': 'Clear',                        'xpath': "//input[@id='clear']",                          'type': 'radio',    'tag': 'input'},
    {'label': 'Obscure',                      'xpath': "//input[@id='obscure']",                        'type': 'radio',    'tag': 'input'},
    {'label': 'Standard A Rated',             'xpath': "//input[@id='arated']",                         'type': 'radio',    'tag': 'input'},
    {'label': 'A+ Rated Energy Upgrade',      'xpath': "//input[@id='aplusrated']",                     'type': 'radio',    'tag': 'input'},
    {'label': 'A++ Triple Glazed',            'xpath': "//input[@id='tripleglazed']",                   'type': 'radio',    'tag': 'input'},
    {'label': 'Toughened Glass',              'xpath': "//input[@id='toughened']",                      'type': 'checkbox', 'tag': 'input'},
    {'label': 'Laminated Glass',              'xpath': "//input[@id='laminated']",                      'type': 'checkbox', 'tag': 'input'},
    {'label': 'Trickle Vents',                'xpath': "//select[@id='tricklevents']",                  'type': '',         'tag': 'select'},
    {'label': 'Fit Pack',                     'xpath': "//input[@id='fitpack']",                        'type': 'checkbox', 'tag': 'input'},
]

# ---------------------------------------------------------------------------
# Comment parser
# ---------------------------------------------------------------------------

def parse_comment(comment: str, labels) -> dict:
    comment_lower = comment.lower()
    result = {}

    dim_match = re.search(r'(\d{3,4})\s*[x×\-\/]\s*(\d{3,4})', comment_lower)
    if dim_match:
        width, height = dim_match.groups()
    else:
        width = height = None

    cill_values = ["No", "85mm", "150mm", "180mm"]
    selected_cill = None
    if "150" in comment_lower or "standard cill" in comment_lower:
        selected_cill = "150mm"
    elif "180" in comment_lower:
        selected_cill = "180mm"
    elif "85" in comment_lower:
        selected_cill = "85mm"
    elif "no cill" in comment_lower:
        selected_cill = "No"

    colours = [
        "White", "Oak Both Sides", "Oak/White", "Rosewood Both Sides",
        "Rosewood/White", "Anthracite Grey Both Sides", "Anthracite Grey/White",
        "Chartwell/White", "Cream Both Sides", "Cream/White",
        "Black-Brown Both Sides", "Black-Brown/White", "Whitegrain Both Sides",
        "Irish Oak Both Sides", "Smooth Anthracite Grey/White", "Agate Grey/White",
    ]
    selected_colour = None
    for colour in colours:
        if colour.lower() in comment_lower and colour.lower() != "white":
            selected_colour = colour
            break

    glass_type = None
    if "clear" in comment_lower:
        glass_type = "Clear"
    if "obscure" in comment_lower:
        glass_type = "Obscure"

    energy = None
    if "triple" in comment_lower:
        energy = "A++ Triple Glazed"
    elif "a+" in comment_lower:
        energy = "A+ Rated"
    elif "a rated" in comment_lower or "a energy" in comment_lower:
        energy = "A Rated"

    toughened = "check" if "toughened" in comment_lower else None
    laminated  = "check" if "laminated"  in comment_lower else None
    fitpack    = "check" if "fit pack"   in comment_lower else None

    vents = "Not Required"
    vent_match = re.search(r'vent[s]?\s*\(?(\d)\)?', comment_lower)
    if vent_match:
        vents = vent_match.group(1)

    ordered_values = [
        width,
        height,
        "check" if selected_cill == "No"    else None,
        "check" if selected_cill == "85mm"  else None,
        "check" if selected_cill == "150mm" else None,
        "check" if selected_cill == "180mm" else None,
        *["check" if colour == selected_colour else None for colour in colours],
        "check" if glass_type == "Clear"           else None,
        "check" if glass_type == "Obscure"         else None,
        "check" if energy == "A Rated"             else None,
        "check" if energy == "A+ Rated"            else None,
        "check" if energy == "A++ Triple Glazed"   else None,
        toughened,
        laminated,
        vents,
        fitpack,
    ]

    for label, value in zip(labels, ordered_values):
        result[label] = value

    return result


# ---------------------------------------------------------------------------
# Helper: smart locator for hidden radio / checkbox inputs
# ---------------------------------------------------------------------------

def _smart_locator(page, step, timeout=5000):
    base = page.locator(f"xpath={step['xpath']}")

    try:
        base.wait_for(state="attached", timeout=2000)
    except Exception:
        return None

    if base.is_visible():
        return base

    element_id = None
    try:
        element_id = base.get_attribute("id")
    except Exception:
        pass

    if element_id:
        icon_div = page.locator(f"label[for='{element_id}'] div[class*='u-check-icon']")
        if icon_div.count() > 0:
            return icon_div.first

        label_for = page.locator(f"label[for='{element_id}']")
        if label_for.count() > 0:
            return label_for.first

    ancestor_label = page.locator(f"xpath={step['xpath']}/ancestor::label")
    if ancestor_label.count() > 0:
        ancestor_icon = ancestor_label.first.locator("div[class*='u-check-icon']")
        if ancestor_icon.count() > 0:
            return ancestor_icon.first
        return ancestor_label.first

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

    wrapper = page.locator(f"xpath={step['xpath']}/ancestor::*[self::div or self::span][1]")
    if wrapper.count() > 0:
        return wrapper.first

    return base


# ---------------------------------------------------------------------------
# Helper: convert simple id-based XPath to CSS selector
# ---------------------------------------------------------------------------

def _xpath_to_css_for_select(xpath: str) -> str:
    m = re.match(r"""//(?:\*|[a-zA-Z]+)\[@id=['"]([^'"]+)['"]\]""", xpath)
    if m:
        return f"#{m.group(1)}"
    return xpath


# ---------------------------------------------------------------------------
# Helper: partial / fuzzy dropdown option selection
# ---------------------------------------------------------------------------

def _select_option_partial(page, xpath: str, target) -> bool:
    css = _xpath_to_css_for_select(xpath)
    target_stripped = str(target).strip()

    boundary_pattern = re.compile(
        r"(?<!\d)" + re.escape(target_stripped) + r"(?!\d)",
        re.IGNORECASE,
    )

    options = page.query_selector_all(f"{css} option")
    if not options:
        # fallback to xpath
        options = page.query_selector_all(f"xpath={xpath}/option")

    for opt in options:
        raw_value   = (opt.get_attribute("value") or "").strip()
        visible_text = (opt.inner_text() or "").strip()

        # Strategy 1 — leading number exact match
        leading = re.match(r"^(\d+(?:\.\d+)?)", raw_value)
        if leading and leading.group(1) == target_stripped:
            page.select_option(css, value=raw_value)
            return True

        # Strategy 2 — word-boundary match on visible text
        if boundary_pattern.search(visible_text):
            page.select_option(css, value=raw_value)
            return True

        # Strategy 3 — word-boundary match on raw value
        if boundary_pattern.search(raw_value):
            page.select_option(css, value=raw_value)
            return True

    # No match — print available options to aid debugging
    print(f"  [debug] No match for '{target_stripped}' in select {xpath}")
    for opt in options:
        print(f"    text='{opt.inner_text().strip()}'  value='{opt.get_attribute('value')}'")
    return False


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------

def scrape_price(
    url: str,
    comment: str,
    price_xpath: str,
    headless: bool = True,
    screenshot_path: str | None = None,
    timeout: int = 30_000,
) -> str:

    labels = [step["label"] for step in STEPS]
    values = parse_comment(comment, labels)

    playwright_instance = sync_playwright().start()
    browser = None

    try:
        browser = playwright_instance.chromium.launch(
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

        # Block heavy resources for faster load
        context.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in {"image", "font", "media"}
            else route.continue_(),
        )

        page = context.new_page()

        # ----- Navigation -----
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        except PlaywrightTimeoutError:
            print("  [warn] domcontentloaded timed out, retrying with 'load'")
            page.goto(url, wait_until="load", timeout=timeout)

        time.sleep(2)  # allow JS frameworks to hydrate

        # ----- Capture old price for change detection -----
        old_price = None
        try:
            price_el = page.locator(f"xpath={price_xpath}")
            price_el.wait_for(state="attached", timeout=3000)
            old_price = price_el.inner_text().strip()
        except Exception:
            pass

        # ----- Execute interaction steps -----
        for idx, step in enumerate(STEPS):
            label = step["label"]
            value = values.get(label)

            if value is None:
                continue  # nothing to do for this field

            tag  = step.get("tag", "input")
            itype = step.get("type", "")

            # --- SELECT ---
            if tag == "select":
                for attempt in range(3):
                    try:
                        matched = _select_option_partial(page, step["xpath"], value)
                        if not matched:
                            raise RuntimeError(
                                f"Step {idx} ('{label}'): no option matched '{value}' "
                                f"in select {step['xpath']}"
                            )
                        break
                    except RuntimeError:
                        raise
                    except Exception as exc:
                        if attempt == 2:
                            raise RuntimeError(
                                f"Step {idx} ('{label}'): select failed after 3 attempts — {exc}"
                            ) from exc
                        time.sleep(1)

                time.sleep(random.uniform(0.5, 1.5))
                continue

            # --- RADIO / CHECKBOX ---
            if itype in ("radio", "checkbox"):
                if str(value).lower() != "check":
                    continue  # only act when explicitly told to check

                locator = _smart_locator(page, step, timeout=5000)
                if locator is None:
                    print(f"  [warn] Step {idx} ('{label}'): element not found, skipping")
                    continue

                try:
                    locator.scroll_into_view_if_needed()
                    locator.click(timeout=timeout)
                except PlaywrightTimeoutError as exc:
                    raise RuntimeError(
                        f"Step {idx} ('{label}'): click timed out on {step['xpath']}"
                    ) from exc

                time.sleep(random.uniform(0.5, 1.5))
                continue

            # --- TEXT INPUT ---
            if itype == "text":
                try:
                    locator = page.locator(f"xpath={step['xpath']}")
                    locator.wait_for(state="visible", timeout=timeout)
                    locator.scroll_into_view_if_needed()
                    locator.click(timeout=timeout)
                    locator.fill(str(value), timeout=timeout)
                    locator.press("Tab")        # trigger change events
                except PlaywrightTimeoutError as exc:
                    raise RuntimeError(
                        f"Step {idx} ('{label}'): text input timed out on {step['xpath']}"
                    ) from exc

                time.sleep(random.uniform(0.5, 1.5))
                continue

        # ----- Wait for price to change -----
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
                pass  # price may be unchanged; extraction will validate

        time.sleep(1)  # small extra settle

        # ----- Extract price -----
        try:
            price_locator = page.locator(f"xpath={price_xpath}").first
            price_locator.wait_for(state="attached", timeout=timeout)
        except PlaywrightTimeoutError as exc:
            raise TimeoutError(
                f"Price element not found at XPath: {price_xpath}"
            ) from exc

        try:
            expect(price_locator).not_to_be_empty(timeout=timeout)
        except (PlaywrightTimeoutError, AssertionError) as exc:
            raise TimeoutError(
                f"Price element found but empty at XPath: {price_xpath}"
            ) from exc

        raw_price = price_locator.inner_text().strip()
        cleaned   = re.sub(r"[€£¥₹,]", "", raw_price).strip()
        print(f"Extracted price: {cleaned}")

        # ----- Screenshot -----
        if screenshot_path:
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"Screenshot saved: {screenshot_path}")

        return cleaned

    finally:
        if browser:
            browser.close()
        playwright_instance.stop()


# ---------------------------------------------------------------------------
# Main block
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
import re
import time
import random

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
    expect,
)

# -------------------------
# Module constants
# -------------------------

PRICE_XPATH = "//span[contains(@class, 'totalpricevisible')]"

STEPS = [
    {'label': 'Frame Width (mm)', 'xpath': "//input[@id='framewidth']", 'type': 'text', 'tag': 'input'},
    {'label': 'Frame Height (mm)', 'xpath': "//input[@id='frameheight']", 'type': 'text', 'tag': 'input'},
    {'label': 'No', 'xpath': "//input[@id='cillno']", 'type': 'radio', 'tag': 'input'},
    {'label': '85mm Stub', 'xpath': "//input[@id='cill85']", 'type': 'radio', 'tag': 'input'},
    {'label': 'Standard 150mm', 'xpath': "//input[@id='cill150']", 'type': 'radio', 'tag': 'input'},
    {'label': '180mm', 'xpath': "//input[@id='cill180']", 'type': 'radio', 'tag': 'input'},
    {'label': 'Oal Rorh Sides', 'xpath': "//input[@id='White']", 'type': 'radio', 'tag': 'input'},
    {'label': 'Anthracite Grev Both Sides', 'xpath': "//input[@id='Oak/White']", 'type': 'radio', 'tag': 'input'},
    {'label': 'Rosewood Both Sides', 'xpath': "//input[@id='Rosewood Both Sides']", 'type': 'radio', 'tag': 'input'},
    {'label': 'Rosewood White', 'xpath': "//input[@id='Rosewood/White']", 'type': 'radio', 'tag': 'input'},
    {'label': 'Anthracite Grev White', 'xpath': "//input[@id='Anthracite Grey/White']", 'type': 'radio', 'tag': 'input'},
    {'label': 'Chartwell White', 'xpath': "//input[@id='Chartwell/White']", 'type': 'radio', 'tag': 'input'},
    {'label': 'Cream Both Sides', 'xpath': "//input[@id='Cream Both Sides']", 'type': 'radio', 'tag': 'input'},
    {'label': 'Black-Brown Both Sides', 'xpath': "//input[@id='Cream/White']", 'type': 'radio', 'tag': 'input'},
    {'label': 'Black-Brown/White', 'xpath': "//input[@id='Black-Brown/White']", 'type': 'radio', 'tag': 'input'},
    {'label': 'Whitegrain Both Sides', 'xpath': "//input[@id='Whitegrain Both Sides']", 'type': 'radio', 'tag': 'input'},
    {'label': 'Smooth Anthracite Grey/White', 'xpath': "//input[@id='Irish Oak Both Sides']", 'type': 'radio', 'tag': 'input'},
    {'label': 'Agate Grey {White', 'xpath': "//input[@id='Agate Grey/White']", 'type': 'radio', 'tag': 'input'},
    {'label': 'Clear', 'xpath': "//input[@id='clear']", 'type': 'radio', 'tag': 'input'},
    {'label': 'Obscure', 'xpath': "//input[@id='obscure']", 'type': 'radio', 'tag': 'input'},
    {'label': 'Standard A Rated', 'xpath': "//input[@id='arated']", 'type': 'radio', 'tag': 'input'},
    {'label': 'A++ Triple Glazed', 'xpath': "//input[@id='tripleglazed']", 'type': 'radio', 'tag': 'input'},
    {'label': 'Toughened Glass', 'xpath': "//input[@id='toughened']", 'type': 'checkbox', 'tag': 'input'},
    {'label': 'Laminated Glass', 'xpath': "//input[@id='laminated']", 'type': 'checkbox', 'tag': 'input'},
    {'label': 'Trickle Vents', 'xpath': "//select[@id='tricklevents']", 'type': '', 'tag': 'select'},
    {'label': 'Fit Pack', 'xpath': "//input[@id='fitpack']", 'type': 'checkbox', 'tag': 'input'},
]

import re
def _click_by_label(page, label_text):

    safe = label_text.lower()

    print("text : ",safe)

    locator = page.locator(
        f"""//label[
            contains(
                translate(normalize-space(.),
                'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                'abcdefghijklmnopqrstuvwxyz'),
                '{safe}'
            )
        ]"""
    ).first

    #locator.scroll_into_view_if_needed()
    locator.click()


def _smart_locator(page, step, timeout=5000):

    base = page.locator(f"xpath={step['xpath']}")

    try:
        base.wait_for(state="attached", timeout=2000)
    except:
        return None

    # visible → use directly
    if base.is_visible():
        return base

    # try label linked via "for"
    element_id = base.get_attribute("id")

    if element_id:
        label_for = page.locator(f"label[for='{element_id}']")
        if label_for.count() > 0:
            return label_for.first

    # try ancestor label
    ancestor_label = page.locator(
        f"xpath={step['xpath']}/ancestor::label"
    )
    if ancestor_label.count() > 0:
        return ancestor_label.first

    # try label by visible text
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
        return label_by_text.first

    # fallback → clickable parent div
    clickable_parent = page.locator(
        f"xpath={step['xpath']}/ancestor::*[self::div or self::span][1]"
    )

    if clickable_parent.count() > 0:
        return clickable_parent.first

    return base
# -------------------------
# comment parser
# -------------------------

def parse_comment(comment: str, labels) -> dict:
    c = comment.lower()

    result = {}

    dim_match = re.search(r"(\d+)\s*[x×]\s*(\d+)", c)

    width = dim_match.group(1) if dim_match else None
    height = dim_match.group(2) if dim_match else None

    cill_selected = "No"
    if "standard" in c:
        cill_selected = "Standard 150mm"

    colour_selected = "White" if "white" in c else None

    glass_selected = "Clear"
    if "obscure" in c:
        glass_selected = "Obscure"

    energy_selected = "Standard A Rated"
    if "triple" in c:
        energy_selected = "A++ Triple Glazed"

    trickle_value = "1" if "trickle" in c else "Not Required"

    toughened_value = "check" if "toughened" in c else None
    laminated_value = "check" if "laminated" in c else None
    fitpack_value = "check" if "fit pack" in c else None

    for label in labels:

        if label == "Frame Width (mm)":
            result[label] = width

        elif label == "Frame Height (mm)":
            result[label] = height

        elif label in ["No", "85mm Stub", "Standard 150mm", "180mm"]:
            result[label] = "check" if label == cill_selected else None

        elif label == "Clear":
            result[label] = "check"

        elif label == "Standard A Rated":
            result[label] = "check"

        elif label == "Trickle Vents":
            result[label] = trickle_value

        elif label == "Fit Pack":
            result[label] = fitpack_value

        elif label == "Toughened Glass":
            result[label] = toughened_value

        elif label == "Laminated Glass":
            result[label] = laminated_value

        else:
            result[label] = None

    return result


# -------------------------
# helpers
# -------------------------

def _xpath_to_css_for_select(xpath: str) -> str:
    m = re.search(r"@id=['\"]([^'\"]+)['\"]", xpath)
    if not m:
        raise ValueError(f"Cannot convert xpath to css: {xpath}")
    return f"#{m.group(1)}"


def _select_option_partial(page, xpath: str, target: str):

    css = _xpath_to_css_for_select(xpath)
    select_el = page.query_selector(css)

    if not select_el:
        raise RuntimeError(f"select not found {xpath}")

    options = select_el.query_selector_all("option")

    target = str(target).strip()

    number_match = re.match(r"^(\d+(?:\.\d+)?)", target)

    boundary_pattern = re.compile(
        r"(?<!\d)" + re.escape(target) + r"(?!\d)",
        re.I,
    )

    for opt in options:

        value = opt.get_attribute("value") or ""
        text = opt.inner_text().strip()

        if number_match:
            leading = re.match(r"^(\d+(?:\.\d+)?)", value)
            if leading and leading.group(1) == number_match.group(1):
                select_el.select_option(value=value)
                return True

        if boundary_pattern.search(text):
            select_el.select_option(value=value)
            return True

        if boundary_pattern.search(value):
            select_el.select_option(value=value)
            return True

    print("Available options:")
    for opt in options:
        print(opt.inner_text(), opt.get_attribute("value"))

    raise RuntimeError(f"no dropdown match for {target}")


# -------------------------
# main function
# -------------------------

def scrape_price(
    url: str,
    comment: str,
    price_xpath: str,
    headless: bool = True,
    screenshot_path: str | None = None,
    timeout: int = 30_000,
) -> str:

    labels = [s["label"] for s in STEPS]

    values = parse_comment(comment, labels)

    playwright = sync_playwright().start()

    try:

        browser = playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

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

        old_price = None

        try:
            old_price = page.locator(f"xpath={price_xpath}").inner_text().strip()
        except:
            pass

        for i, step in enumerate(STEPS):

            label = step["label"]
            value = values.get(label)

            if value is None:
                continue

           # locator = page.locator(f"xpath={step['xpath']}")
            locator = _smart_locator(page, step, timeout=timeout)
            print(f"Processing step {i+1}/{len(STEPS)}: {label} = {value}")

            try:

                if step["tag"] == "input":

                    if step["type"] == "text":
                        locator.wait_for(state="visible", timeout=timeout)
                        locator.fill(str(value))

                    elif step["type"] in ("radio", "checkbox"):

                        if value == "check":
                            print(f"Checking {label}")
                            locator.wait_for(state="visible", timeout=timeout)
                            locator.click()
                            #_click_by_label(page, step["label"])
                                        
                elif step["tag"] == "select":

                    for attempt in range(3):

                        try:
                            _select_option_partial(page, step["xpath"], value)
                            break
                        except RuntimeError:
                            raise
                        except Exception:
                            time.sleep(1)

                time.sleep(random.uniform(0.5, 1.5))

            except PlaywrightTimeoutError as e:
                raise RuntimeError(
                    f"Step {i} failed {label} {step['xpath']}"
                ) from e

        if old_price:

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

        price_locator = page.locator(f"xpath={price_xpath}").first

        price_locator.wait_for(state="attached", timeout=timeout)

        expect(price_locator).not_to_be_empty(timeout=timeout)

        price = price_locator.inner_text().strip()

        price = re.sub(r"[^\d.]", "", price)

        print("Extracted price:", price)

        if screenshot_path:
            page.screenshot(path=screenshot_path, full_page=True)
            print("Saved screenshot:", screenshot_path)

        return price

    finally:
        browser.close()
        playwright.stop()


# -------------------------
# run
# -------------------------

if __name__ == "__main__":

    url = input("Enter URL: ")

    comment = input("comment : ")

    price = scrape_price(
        url=url,
        comment=comment,
        price_xpath=PRICE_XPATH,
        headless=False,
        screenshot_path="price_screenshot.png",
        timeout=20_000,
    )

    print("Final price:", price)
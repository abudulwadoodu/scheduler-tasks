import re
import time
import random
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, expect

# =========================
# CONSTANTS
# =========================
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

# =========================
# PARSER (your function reused)
# =========================
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
# =========================
# SMART LOCATOR
# =========================
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

# =========================
# DROPDOWN SELECT
# =========================
def _select_option_partial(page, xpath, target):
    target = str(target).strip()
    select = page.locator(f"xpath={xpath}")
    options = select.locator("option")

    for i in range(options.count()):
        opt = options.nth(i)
        value = opt.get_attribute("value") or ""
        text = opt.inner_text()

        if target in text or target in value:
            select.select_option(value=value)
            return True

    raise RuntimeError(f"No match for dropdown: {target}")

# =========================
# MAIN FUNCTION
# =========================
def scrape_price(
    url: str,
    comment: str,
    price_xpath: str,
    headless: bool = True,
    screenshot_path: str | None = None,
    timeout: int = 30000,
) -> str:

    labels = [step["label"] for step in STEPS]
    values = parse_comment(comment, labels)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
        )

        context.route("**/*", lambda route: route.abort()
            if route.request.resource_type in {"image", "font", "media"}
            else route.continue_())

        page = context.new_page()

        try:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            except:
                page.goto(url, wait_until="load", timeout=timeout)

            time.sleep(2)

            # old price
            old_price = None
            try:
                el = page.locator(f"xpath={price_xpath}")
                if el.count() > 0:
                    old_price = el.first.inner_text().strip()
            except:
                pass

            # =========================
            # EXECUTE STEPS
            # =========================
            for i, step in enumerate(STEPS):
                value = values.get(step["label"])

                if value is None:
                    continue

                locator = _smart_locator(page, step)
                if not locator:
                    raise RuntimeError(f"Step {i} element not found")

                locator.scroll_into_view_if_needed()

                if step["tag"] == "input" and step["type"] == "text":
                    locator.fill(str(value))

                elif step["type"] in ["radio", "checkbox"]:
                    if value == "check":
                        locator.click()

                elif step["tag"] == "select":
                    for _ in range(3):
                        try:
                            _select_option_partial(page, step["xpath"], value)
                            break
                        except Exception:
                            time.sleep(1)

                time.sleep(random.uniform(0.5, 1.5))

            # =========================
            # WAIT FOR PRICE CHANGE
            # =========================
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

            # =========================
            # EXTRACT PRICE
            # =========================
            price_locator = page.locator(f"xpath={price_xpath}").first
            price_locator.wait_for(state="attached", timeout=timeout)
            expect(price_locator).not_to_be_empty(timeout=timeout)

            price = price_locator.inner_text().strip()
            price = re.sub(r"[^\d.]", "", price)

            print(f"Extracted price: {price}")

            if screenshot_path:
                page.screenshot(path=screenshot_path, full_page=True)
                print(f"Screenshot saved: {screenshot_path}")

            return price

        finally:
            browser.close()


# =========================
# MAIN
# =========================
if __name__ == "__main__":

    url = input("Enter URL: ")
    comment = input("comment : ")

    price = scrape_price(
        url=url,
        comment=comment,
        price_xpath=PRICE_XPATH,
        headless=False,
        screenshot_path="price_screenshot.png",
        timeout=20000,
    )

    print(f"Final price: {price}")
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

# Pydantic model
from typing import Optional
from pydantic import BaseModel, Field
class NagivationStepsModel(BaseModel):
    model_config = {"populate_by_name": True}
    # -- Dimensions --
    Frame_Width_mm: Optional[str] = Field(default=None, alias="Frame Width (mm)")
    Frame_Height_mm: Optional[str] = Field(default=None, alias="Frame Height (mm)")

    # -- Cill Options --
    No: Optional[bool] = Field(default=None, alias="No")
    mm_Stub: Optional[bool] = Field(default=None, alias="85mm Stub")
    Standard_150mm: Optional[bool] = Field(default=None, alias="Standard 150mm")
    mm80: Optional[bool] = Field(default=None, alias="180mm")

    # -- Colour Options --
    White: Optional[bool] = Field(default=None, alias="White")
    Oak_Both_Sides: Optional[bool] = Field(default=None, alias="Oak Both Sides")
    Oak_White: Optional[bool] = Field(default=None, alias="Oak/White")
    Rosewood_Both_Sides: Optional[bool] = Field(default=None, alias="Rosewood Both Sides")
    Rosewood_White: Optional[bool] = Field(default=None, alias="Rosewood/White")
    Anthracite_Grey_Both_Sides: Optional[bool] = Field(default=None, alias="Anthracite Grey Both Sides")
    Anthracite_Grey_White: Optional[bool] = Field(default=None, alias="Anthracite Grey/White")
    Chartwell_White: Optional[bool] = Field(default=None, alias="Chartwell/White")
    Cream_Both_Sides: Optional[bool] = Field(default=None, alias="Cream Both Sides")
    Cream_White: Optional[bool] = Field(default=None, alias="Cream/White")
    Black_Brown_Both_Sides: Optional[bool] = Field(default=None, alias="Black-Brown Both Sides")
    Black_Brown_White: Optional[bool] = Field(default=None, alias="Black-Brown/White")
    Whitegrain_Both_Sides: Optional[bool] = Field(default=None, alias="Whitegrain Both Sides")
    Irish_Oak_Both_Sides: Optional[bool] = Field(default=None, alias="Irish Oak Both Sides")
    Smooth_Anthracite_Grey_White: Optional[bool] = Field(default=None, alias="Smooth Anthracite Grey/White")
    Agate_Grey_White: Optional[bool] = Field(default=None, alias="Agate Grey/White")

    # -- Glass Type --
    Clear: Optional[bool] = Field(default=None, alias="Clear")
    Obscure: Optional[bool] = Field(default=None, alias="Obscure")

    # -- Energy Rating --
    Standard_A_Rated: Optional[bool] = Field(default=None, alias="Standard A Rated")
    A_Plus_Rated_Energy_Upgrade: Optional[bool] = Field(default=None, alias="A+ Rated Energy Upgrade")
    A_Plus_Plus_Triple_Glazed: Optional[bool] = Field(default=None, alias="A++ Triple Glazed")

    # -- Glass Upgrades --
    Toughened_Glass: Optional[bool] = Field(default=None, alias="Toughened Glass")
    Laminated_Glass: Optional[bool] = Field(default=None, alias="Laminated Glass")

    # -- Extras --
    Trickle_Vents: str = Field(default="", alias="Trickle Vents")
    Fit_Pack: Optional[bool] = Field(default=None, alias="Fit Pack")

# =========================
# COMMENT PARSER
# =========================
import re
def parse_comment(comment: str) -> NagivationStepsModel:
    c = comment.lower()

    # --- Dimensions ---
    dim = re.search(r'(\d+)\s*(?:mm)?\s*[x×]\s*(\d+)\s*(?:mm)?', c)
    width, height = (dim.group(1), dim.group(2)) if dim else (None, None)

    # --- Cill Options ---
    if '180mm' in c or '180 mm' in c:
        selected_cill = 'mm80'
    elif '150mm' in c or '150 mm' in c or 'standard cill' in c or 'standard 150' in c:
        selected_cill = 'Standard_150mm'
    elif '85mm' in c or 'stub' in c:
        selected_cill = 'mm_Stub'
    elif 'no cill' in c or 'without cill' in c:
        selected_cill = 'No'
    else:
        selected_cill = 'Standard_150mm'

    # --- Colour Options ---
    # match-order: most specific first
    colour_match_order = [
        ('smooth anthracite grey/white', 'Smooth_Anthracite_Grey_White'),
        ('smooth anthracite grey / white', 'Smooth_Anthracite_Grey_White'),
        ('agate grey/white', 'Agate_Grey_White'),
        ('agate grey / white', 'Agate_Grey_White'),
        ('anthracite grey both sides', 'Anthracite_Grey_Both_Sides'),
        ('anthracite grey/white', 'Anthracite_Grey_White'),
        ('anthracite grey / white', 'Anthracite_Grey_White'),
        ('anthracite grey', 'Anthracite_Grey_White'),
        ('chartwell/white', 'Chartwell_White'),
        ('chartwell / white', 'Chartwell_White'),
        ('chartwell', 'Chartwell_White'),
        ('black-brown both sides', 'Black_Brown_Both_Sides'),
        ('black-brown/white', 'Black_Brown_White'),
        ('black-brown / white', 'Black_Brown_White'),
        ('black brown both sides', 'Black_Brown_Both_Sides'),
        ('black brown/white', 'Black_Brown_White'),
        ('black-brown', 'Black_Brown_White'),
        ('rosewood both sides', 'Rosewood_Both_Sides'),
        ('rosewood/white', 'Rosewood_White'),
        ('rosewood / white', 'Rosewood_White'),
        ('rosewood', 'Rosewood_White'),
        ('irish oak both sides', 'Irish_Oak_Both_Sides'),
        ('irish oak', 'Irish_Oak_Both_Sides'),
        ('oak both sides', 'Oak_Both_Sides'),
        ('oak/white', 'Oak_White'),
        ('oak / white', 'Oak_White'),
        ('oak', 'Oak_White'),
        ('cream both sides', 'Cream_Both_Sides'),
        ('cream/white', 'Cream_White'),
        ('cream / white', 'Cream_White'),
        ('cream', 'Cream_White'),
        ('whitegrain both sides', 'Whitegrain_Both_Sides'),
        ('whitegrain', 'Whitegrain_Both_Sides'),
        ('white upvc', None),
        ('white', None),
    ]
    # field-name order (for output)
    colour_field_order = [
        'White', 'Oak_Both_Sides', 'Oak_White', 'Rosewood_Both_Sides', 'Rosewood_White',
        'Anthracite_Grey_Both_Sides', 'Anthracite_Grey_White', 'Chartwell_White',
        'Cream_Both_Sides', 'Cream_White', 'Black_Brown_Both_Sides', 'Black_Brown_White',
        'Whitegrain_Both_Sides', 'Irish_Oak_Both_Sides',
        'Smooth_Anthracite_Grey_White', 'Agate_Grey_White',
    ]

    selected_colour = None
    base_white = False
    for pattern, field in colour_match_order:
        if pattern in c:
            if field is None:
                base_white = True
            else:
                selected_colour = field
            break

    # --- Glass Type ---
    if 'obscure' in c:
        selected_glass = 'Obscure'
    else:
        selected_glass = 'Clear'

    # --- Energy Rating ---
    if 'a++' in c or 'triple glazed' in c or 'triple-glazed' in c:
        selected_rating = 'A_Plus_Plus_Triple_Glazed'
    elif 'a+' in c:
        selected_rating = 'A_Plus_Rated_Energy_Upgrade'
    elif 'a rated' in c or 'a-rated' in c or 'a energy' in c:
        selected_rating = 'Standard_A_Rated'
    else:
        selected_rating = 'Standard_A_Rated'

    # --- Glass Upgrades (checkboxes) ---
    toughened = True if 'toughened' in c else None
    laminated = True if 'laminated' in c else None

    # --- Trickle Vents (select) ---
    trickle_options = ['1', '2', '3', '4', '5', '6']
    trickle_vents = ''
    if 'trickle vent' in c or 'trickle vents' in c:
        qty_match = re.search(r'trickle\s+vents?\s*[(\[]?\s*(\d+)\s*[)\]]?|[(\[x×]\s*(\d+)\s*[)\]]?\s*trickle|(\d+)\s*[x×]\s*trickle', c)
        if not qty_match:
            qty_match = re.search(r'vents?\s*[(\[]?\s*(\d+)', c)
        if qty_match:
            qty = next(g for g in qty_match.groups() if g is not None)
            trickle_vents = qty if qty in trickle_options else '1'
        else:
            trickle_vents = '1'

    # --- Fit Pack (checkbox) ---
    fit_pack = True if 'fit pack' in c else None

    # --- Build and return model ---
    return NagivationStepsModel(
        Frame_Width_mm=width,
        Frame_Height_mm=height,
        No=True if selected_cill == 'No' else None,
        mm_Stub=True if selected_cill == 'mm_Stub' else None,
        Standard_150mm=True if selected_cill == 'Standard_150mm' else None,
        mm80=True if selected_cill == 'mm80' else None,
        **{
            field: (True if (not base_white and field == selected_colour) else None)
            for field in colour_field_order
        },
        Clear=True if selected_glass == 'Clear' else None,
        Obscure=True if selected_glass == 'Obscure' else None,
        Standard_A_Rated=True if selected_rating == 'Standard_A_Rated' else None,
        A_Plus_Rated_Energy_Upgrade=True if selected_rating == 'A_Plus_Rated_Energy_Upgrade' else None,
        A_Plus_Plus_Triple_Glazed=True if selected_rating == 'A_Plus_Plus_Triple_Glazed' else None,
        Toughened_Glass=toughened,
        Laminated_Glass=laminated,
        Trickle_Vents=trickle_vents,
        Fit_Pack=fit_pack,
    )

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
        icon_div = page.locator(
            f"label[for='{element_id}'] div[class*='u-check-icon']"
        )
        if icon_div.count() > 0:
            return icon_div.first

        label_for = page.locator(f"label[for='{element_id}']")
        if label_for.count() > 0:
            return label_for.first

    ancestor_label = page.locator(
        f"xpath={step['xpath']}/ancestor::label"
    )
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

    wrapper = page.locator(
        f"xpath={step['xpath']}/ancestor::*[self::div or self::span][1]"
    )
    if wrapper.count() > 0:
        return wrapper.first

    return base


# =========================
# DROPDOWN SELECT
# =========================
def _xpath_to_css_for_select(xpath: str) -> str:
    m = re.search(r"\[@id='([^']+)'\]", xpath)
    return f"#{m.group(1)}" if m else xpath


def _select_option_partial(page, xpath: str, target, step_index: int) -> bool:
    css = _xpath_to_css_for_select(xpath)
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

            print(f"[DEBUG] Step {step_index}: no option matched '{target_stripped}'")
            for opt in options:
                print(f"  text={opt.inner_text()!r:40s}  value={opt.get_attribute('value')!r}")
            raise RuntimeError(
                f"Step {step_index}: no option matching '{target_stripped}' found in {xpath}"
            )

        except RuntimeError:
            raise
        except Exception as exc:
            if attempt == 2:
                raise RuntimeError(
                    f"Step {step_index}: select failed after 3 attempts - {exc}"
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

    model = parse_comment(comment)
    values = model.model_dump(by_alias=True)

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
                price_el = page.locator(f"xpath={price_xpath}")
                price_el.wait_for(state="attached", timeout=3000)
                old_price = price_el.inner_text().strip()
            except Exception:
                pass

            # =========================
            # EXECUTE STEPS
            # =========================
            for idx, step in enumerate(STEPS):
                label = step["label"]
                value = values.get(label)

                if value is None:
                    continue

                tag   = step.get("tag", "input")
                itype = step.get("type", "")

                if tag == "select":
                    _select_option_partial(page, step["xpath"], value, idx)
                    _random_delay()
                    continue

                if itype == "text":
                    locator = page.locator(f"xpath={step['xpath']}")
                    try:
                        locator.wait_for(state="visible", timeout=timeout)
                    except PlaywrightTimeoutError:
                        raise RuntimeError(
                            f"Step {idx}: timeout waiting for text input - {step['xpath']}"
                        )
                    locator.scroll_into_view_if_needed()
                    locator.click()
                    locator.type(str(value), delay=50)
                    _random_delay()
                    continue

                if value != True:
                    continue

                smart = _smart_locator(page, step, timeout=timeout)
                if smart is None:
                    print(f"[WARN] Step {idx}: could not resolve locator for '{label}' - skipping")
                    continue

                try:
                    smart.scroll_into_view_if_needed()
                    smart.click(timeout=timeout)
                except PlaywrightTimeoutError as exc:
                    raise RuntimeError(
                        f"Step {idx}: timeout clicking '{itype}' element - {step['xpath']}"
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
            price_locator = page.locator(f"xpath={price_xpath}").first
            try:
                price_locator.wait_for(state="attached", timeout=timeout)
            except PlaywrightTimeoutError:
                raise TimeoutError(f"Price element not found: {price_xpath}")

            try:
                expect(price_locator).not_to_be_empty(timeout=timeout)
            except (PlaywrightTimeoutError, AssertionError):
                raise TimeoutError(f"Price element found but empty: {price_xpath}")

            raw_price = price_locator.inner_text().strip()
            cleaned   = re.sub(r"[€£¥₹,]", "", raw_price).strip()

            print(f"Extracted price: {cleaned}")

            if screenshot_path:
                page.screenshot(path=screenshot_path, full_page=True)
                print(f"Screenshot saved: {screenshot_path}")

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
    print(f"Final price: {price}")

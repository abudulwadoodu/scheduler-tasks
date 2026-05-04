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
- For numerical values take numerical values from the comment and convert to string (e.g. "630mm" → "630")
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
# ── Pydantic Model ────────────────────────────────────────────────────────────

class NagivationStepsModel(BaseModel):
    model_config = {"populate_by_name": True}

    # -- Dimensions --
    Frame_Width_mm: Optional[str] = Field(default=None, alias="Frame Width (mm)")
    Frame_Height_mm: Optional[str] = Field(default=None, alias="Frame Height (mm)")
    # -- Cill Options --
    No: Optional[bool] = Field(default=None, alias="No")
    mm85_Stub: Optional[bool] = Field(default=None, alias="85mm Stub")
    Standard_150mm: Optional[bool] = Field(default=None, alias="Standard 150mm")
    mm180: Optional[bool] = Field(default=None, alias="180mm")
    # -- Colour Options --
    White: Optional[bool] = Field(default=None, alias="White")
    Oak_Both_Sides: Optional[bool] = Field(default=None, alias="Oak Both Sides")
    Oak_White: Optional[bool] = Field(default=None, alias="Oak/White")
    Rosewood_Both_Sides: Optional[bool] = Field(default=None, alias="Rosewood Both Sides")
    Rosewood_White: Optional[bool] = Field(default=None, alias="Rosewood/White")
    Anthracite_Grev_Both_Sides: Optional[bool] = Field(default=None, alias="Anthracite Grev Both Sides")
    Anthracite_Grev_White: Optional[bool] = Field(default=None, alias="Anthracite Grev/White")
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
    A_Rated_Energy_Upgrade: Optional[bool] = Field(default=None, alias="A+ Rated Energy Upgrade")
    A_Triple_Glazed: Optional[bool] = Field(default=None, alias="A++ Triple Glazed")
    # -- Glass Add-ons --
    Toughened_Glass: Optional[bool] = Field(default=None, alias="Toughened Glass")
    Laminated_Glass: Optional[bool] = Field(default=None, alias="Laminated Glass")
    # -- Ventilation --
    Trickle_Vents: Literal["Not Required", "1", "2"] = Field(default="Not Required", alias="Trickle Vents")
    # -- Accessories --
    Fit_Pack: Optional[bool] = Field(default=None, alias="Fit Pack")

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{comment}"),
])


# ── Parser Function ───────────────────────────────────────────────────────────

def parse_order_from_comment(comment: str) -> NagivationStepsModel:
    """
    Uses LangChain with OpenAI structured output.
    The Pydantic model is passed directly as the output schema.
    Returns a fully validated NagivationStepsModel instance.
    """
    llm = ChatOpenAI(model="gpt-5.2", temperature=0)

    # with_structured_output passes the Pydantic model as the schema
    # and returns a validated Pydantic object directly
    structured_llm = llm.with_structured_output(NagivationStepsModel)

    chain = prompt | structured_llm

    return chain.invoke({"comment": comment})

# =========================
# COMMENT PARSER
# =========================
def parse_comment(comment: str) -> NagivationStepsModel:
    c = comment.lower()
    # --- Dimensions ---
    dim = re.search(r'(\d+)\s*[x×/-]\s*(\d+)', c)
    if dim:
        width, height = dim.group(1), dim.group(2)
    else:
        return parse_order_from_comment(comment)
    # --- Cill Options ---
    if '85mm stub' in c:
        cill_no, cill_85mm, cill_150mm, cill_180mm = None, True, None, None
    elif 'standard 150mm' in c:
        cill_no, cill_85mm, cill_150mm, cill_180mm = None, None, True, None
    elif '180mm' in c:
        cill_no, cill_85mm, cill_150mm, cill_180mm = None, None, None, True
    else:
        cill_no, cill_85mm, cill_150mm, cill_180mm = True, None, None, None
    # --- Colour Options ---
    colours = ['white', 'oak both sides', 'oak/white', 'rosewood both sides', 'rosewood/white',
               'anthracite grey both sides', 'anthracite grey/white', 'chartwell/white', 'cream both sides',
               'cream/white', 'black-brown both sides', 'black-brown/white', 'whitegrain both sides',
               'irish oak both sides', 'smooth anthracite grey/white', 'agate grey/white']
    colour_fields = ['White', 'Oak_Both_Sides', 'Oak_White', 'Rosewood_Both_Sides', 'Rosewood_White',
                     'Anthracite_Grev_Both_Sides', 'Anthracite_Grev_White', 'Chartwell_White', 'Cream_Both_Sides',
                     'Cream_White', 'Black_Brown_Both_Sides', 'Black_Brown_White', 'Whitegrain_Both_Sides',
                     'Irish_Oak_Both_Sides', 'Smooth_Anthracite_Grey_White', 'Agate_Grey_White']
    if 'white upvc' in c:
        colour_values = [None] * len(colour_fields)
    else:
        colour_values = [True if colour in c else None for colour in colours]
    # --- Glass Type ---
    if 'obscure' in c:
        clear, obscure = None, True
    else:
        clear, obscure = True, None
    # --- Energy Rating ---
    if 'a++ triple glazed' in c:
        energy_standard, energy_upgrade, energy_triple = None, None, True
    elif 'a+ rated energy upgrade' in c:
        energy_standard, energy_upgrade, energy_triple = None, True, None
    else:
        energy_standard, energy_upgrade, energy_triple = True, None, None
    # --- Glass Add-ons ---
    toughened_glass = True if 'toughened glass' in c else None
    laminated_glass = True if 'laminated glass' in c else None
    # --- Ventilation ---
    trickle_vents = 'Not Required'
    vent_match = re.search(r'(\d+)\s*trickle vents|trickle vents\s*(\d+)|x(\d+)|(\d+)x|\((\d+)\)|\[(\d+)\]', c)
    if vent_match:
        vent_qty = next(g for g in vent_match.groups() if g is not None)
        trickle_vents = vent_qty if vent_qty in ('1', '2') else 'Not Required'
    elif 'trickle vent' in c:
        return parse_order_from_comment(comment)
    # --- Accessories ---
    fit_pack = True if 'fit pack' in c else None
    # --- Build and return model ---
    return NagivationStepsModel(
        Frame_Width_mm=width,
        Frame_Height_mm=height,
        No=cill_no,
        mm85_Stub=cill_85mm,
        Standard_150mm=cill_150mm,
        mm180=cill_180mm,
        White=colour_values[0],
        Oak_Both_Sides=colour_values[1],
        Oak_White=colour_values[2],
        Rosewood_Both_Sides=colour_values[3],
        Rosewood_White=colour_values[4],
        Anthracite_Grev_Both_Sides=colour_values[5],
        Anthracite_Grev_White=colour_values[6],
        Chartwell_White=colour_values[7],
        Cream_Both_Sides=colour_values[8],
        Cream_White=colour_values[9],
        Black_Brown_Both_Sides=colour_values[10],
        Black_Brown_White=colour_values[11],
        Whitegrain_Both_Sides=colour_values[12],
        Irish_Oak_Both_Sides=colour_values[13],
        Smooth_Anthracite_Grey_White=colour_values[14],
        Agate_Grey_White=colour_values[15],
        Clear=clear,
        Obscure=obscure,
        Standard_A_Rated=energy_standard,
        A_Rated_Energy_Upgrade=energy_upgrade,
        A_Triple_Glazed=energy_triple,
        Toughened_Glass=toughened_glass,
        Laminated_Glass=laminated_glass,
        Trickle_Vents=trickle_vents,
        Fit_Pack=fit_pack
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
        f"xpath={{step['xpath']}}/ancestor::label"
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
    return f"#{{m.group(1)}}" if m else xpath


def _select_option_partial(page, xpath: str, target, step_index: int) -> bool:
    css = _xpath_to_css_for_select(xpath)
    target_stripped = str(target).strip()

    boundary_pattern = re.compile(
        r"(?<!\d)" + re.escape(target_stripped) + r"(?!\d)",
        re.IGNORECASE,
    )

    for attempt in range(3):
        try:
            options = page.query_selector_all(f"{{css}} option")
            if not options:
                raise RuntimeError(
                    f"Step {{step_index}}: no <option> elements found in select {{xpath}}"
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

            print(f"[DEBUG] Step {{step_index}}: no option matched '{{target_stripped}}'")
            for opt in options:
                print(f"  text={{opt.inner_text()!r:40s}}  value={{opt.get_attribute('value')!r}}")
            raise RuntimeError(
                f"Step {{step_index}}: no option matching '{{target_stripped}}' found in {{xpath}}"
            )

        except RuntimeError:
            raise
        except Exception as exc:
            if attempt == 2:
                raise RuntimeError(
                    f"Step {{step_index}}: select failed after 3 attempts - {{exc}}"
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
                price_el = page.locator(f"xpath={{price_xpath}}")
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

            print(f"Extracted price: {{cleaned}}")

            if screenshot_path:
                page.screenshot(path=screenshot_path, full_page=True)
                print(f"Screenshot saved: {{screenshot_path}}")

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
    print(f"Final price: {{price}}")

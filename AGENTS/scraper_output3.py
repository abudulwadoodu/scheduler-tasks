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
PRICE_XPATH = '//div[contains(@class, "card g-brd-primary rounded-0 g-mb-15 d-none d-sm-block")]'

STEPS = [{'label': 'Frame Width (mm)', 'xpath': '//*[@id="framewidth"]', 'type': 'text', 'tag': 'input'}, {'label': 'Frame Height (mm)', 'xpath': '//*[@id="frameheight"]', 'type': 'text', 'tag': 'input'}, {'label': 'No', 'xpath': '//*[@id="cillno"]', 'type': 'radio', 'tag': 'input'}, {'label': '85mm Stub', 'xpath': '//*[@id="cill85"]', 'type': 'radio', 'tag': 'input'}, {'label': 'Standard 150mm', 'xpath': '//*[@id="cill150"]', 'type': 'radio', 'tag': 'input'}, {'label': '180mm', 'xpath': '//*[@id="cill180"]', 'type': 'radio', 'tag': 'input'}, {'label': 'White', 'xpath': '//*[@id="White"]', 'type': 'radio', 'tag': 'input'}, {'label': 'Oak Both Sides', 'xpath': '//*[@id="Oak Both Sides"]', 'type': 'radio', 'tag': 'input'}, {'label': 'Oak/White', 'xpath': '//*[@id="Oak/White"]', 'type': 'radio', 'tag': 'input'}, {'label': 'Rosewood Both Sides', 'xpath': '//*[@id="Rosewood Both Sides"]', 'type': 'radio', 'tag': 'input'}, {'label': 'Rosewood/White', 'xpath': '//*[@id="Rosewood/White"]', 'type': 'radio', 'tag': 'input'}, {'label': 'Anthracite Grev Both Sides', 'xpath': '//*[@id="Anthracite Grey Both Sides"]', 'type': 'radio', 'tag': 'input'}, {'label': 'Anthracite Grev/White', 'xpath': '//*[@id="Anthracite Grey/White"]', 'type': 'radio', 'tag': 'input'}, {'label': 'Chartwell/White', 'xpath': '//*[@id="Chartwell/White"]', 'type': 'radio', 'tag': 'input'}, {'label': 'Cream Both Sides', 'xpath': '//*[@id="Cream Both Sides"]', 'type': 'radio', 'tag': 'input'}, {'label': 'Cream/White', 'xpath': '//*[@id="Cream/White"]', 'type': 'radio', 'tag': 'input'}, {'label': 'Black-Brown Both Sides', 'xpath': '//*[@id="Black-Brown Both Sides"]', 'type': 'radio', 'tag': 'input'}, {'label': 'Black-Brown/White', 'xpath': '//*[@id="Black-Brown/White"]', 'type': 'radio', 'tag': 'input'}, {'label': 'Whitegrain Both Sides', 'xpath': '//*[@id="Whitegrain Both Sides"]', 'type': 'radio', 'tag': 'input'}, {'label': 'Irish Oak Both Sides', 'xpath': '//*[@id="Irish Oak Both Sides"]', 'type': 'radio', 'tag': 'input'}, {'label': 'Smooth Anthracite Grey/White', 'xpath': '//*[@id="Smooth Anthracite Grey/White"]', 'type': 'radio', 'tag': 'input'}, {'label': 'Agate Grey/White', 'xpath': '//*[@id="Agate Grey/White"]', 'type': 'radio', 'tag': 'input'}, {'label': 'Clear', 'xpath': '//*[@id="clear"]', 'type': 'radio', 'tag': 'input'}, {'label': 'Obscure', 'xpath': '//*[@id="obscure"]', 'type': 'radio', 'tag': 'input'}, {'label': 'Standard A Rated', 'xpath': '//*[@id="arated"]', 'type': 'radio', 'tag': 'input'}, {'label': 'A+ Rated Energy Upgrade', 'xpath': '//*[@id="aplusrated"]', 'type': 'radio', 'tag': 'input'}, {'label': 'A++ Triple Glazed', 'xpath': '//*[@id="tripleglazed"]', 'type': 'radio', 'tag': 'input'}, {'label': 'Toughened Glass', 'xpath': '//*[@id="toughened"]', 'type': 'checkbox', 'tag': 'input'}, {'label': 'Laminated Glass', 'xpath': '//*[@id="laminated"]', 'type': 'checkbox', 'tag': 'input'}, {'label': 'Trickle Vents', 'xpath': '//*[@id="tricklevents"]', 'type': '', 'tag': 'select'}, {'label': 'Fit Pack', 'xpath': '//*[@id="fitpack"]', 'type': 'checkbox', 'tag': 'input'}]

# Pydantic model
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

class NagivationStepsModel(BaseModel):
    model_config = {"populate_by_name": True}

    Frame_Width_mm: Optional[str] = Field(None, alias="Frame Width (mm)")
    Frame_Height_mm: Optional[str] = Field(None, alias="Frame Height (mm)")
    No: Optional[bool] = Field(None, alias="No")
    mm85_Stub: Optional[bool] = Field(None, alias="85mm Stub")
    Standard_mm150: Optional[bool] = Field(None, alias="Standard 150mm")
    mm180: Optional[bool] = Field(None, alias="180mm")
    White: Optional[bool] = Field(None, alias="White")
    Oak_Both_Sides: Optional[bool] = Field(None, alias="Oak Both Sides")
    Oak_White: Optional[bool] = Field(None, alias="Oak/White")
    Rosewood_Both_Sides: Optional[bool] = Field(None, alias="Rosewood Both Sides")
    Rosewood_White: Optional[bool] = Field(None, alias="Rosewood/White")
    Anthracite_Grey_Both_Sides: Optional[bool] = Field(None, alias="Anthracite Grey Both Sides")
    Anthracite_Grey_White: Optional[bool] = Field(None, alias="Anthracite Grey/White")
    Chartwell_White: Optional[bool] = Field(None, alias="Chartwell/White")
    Cream_Both_Sides: Optional[bool] = Field(None, alias="Cream Both Sides")
    Cream_White: Optional[bool] = Field(None, alias="Cream/White")
    Black_Brown_Both_Sides: Optional[bool] = Field(None, alias="Black-Brown Both Sides")
    Black_Brown_White: Optional[bool] = Field(None, alias="Black-Brown/White")
    Whitegrain_Both_Sides: Optional[bool] = Field(None, alias="Whitegrain Both Sides")
    Irish_Oak_Both_Sides: Optional[bool] = Field(None, alias="Irish Oak Both Sides")
    Smooth_Anthracite_Grey_White: Optional[bool] = Field(None, alias="Smooth Anthracite Grey/White")
    Agate_Grey_White: Optional[bool] = Field(None, alias="Agate Grey/White")
    Clear: Optional[bool] = Field(None, alias="Clear")
    Obscure: Optional[bool] = Field(None, alias="Obscure")
    Standard_A_Rated: Optional[bool] = Field(None, alias="Standard A Rated")
    A_Plus_Rated_Energy_Upgrade: Optional[bool] = Field(None, alias="A+ Rated Energy Upgrade")
    A_Plus_Plus_Triple_Glazed: Optional[bool] = Field(None, alias="A++ Triple Glazed")
    Toughened_Glass: Optional[bool] = Field(None, alias="Toughened Glass")
    Laminated_Glass: Optional[bool] = Field(None, alias="Laminated Glass")
    Trickle_Vents: str = Field("", alias="Trickle Vents")
    Fit_Pack: Optional[bool] = Field(None, alias="Fit Pack")

    @field_validator("Trickle_Vents", mode="before")
    def validate_trickle_vents(cls, v):
        map_ = {
            "Not Required": "Not Required",
            "1": "1",
            "2": "2"
        }
        return map_.get(str(v), str(v))

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{comment}"),
])


# ── Fallback Parser ───────────────────────────────────────────────────────────

def parse_order_from_comment(comment: str) -> NagivationStepsModel:
    """
    Uses LangChain with OpenAI structured output.
    Returns a fully validated NagivationStepsModel instance.
    """
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
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
    # --- Radio group ---
    if '85mm stub' in c:
        selected_cill = '85mm Stub'
    elif 'standard 150mm' in c:
        selected_cill = 'Standard 150mm'
    elif '180mm' in c:
        selected_cill = '180mm'
    else:
        selected_cill = None
    # --- Colour group ---
    colours = ['white', 'oak both sides', 'oak/white', 'rosewood both sides', 'rosewood/white',
               'anthracite grey both sides', 'anthracite grey/white', 'chartwell/white',
               'cream both sides', 'cream/white', 'black-brown both sides', 'black-brown/white',
               'whitegrain both sides', 'irish oak both sides', 'smooth anthracite grey/white',
               'agate grey/white']
    colour_fields = ['White', 'Oak_Both_Sides', 'Oak_White', 'Rosewood_Both_Sides', 'Rosewood_White',
                     'Anthracite_Grey_Both_Sides', 'Anthracite_Grey_White', 'Chartwell_White',
                     'Cream_Both_Sides', 'Cream_White', 'Black_Brown_Both_Sides', 'Black_Brown_White',
                     'Whitegrain_Both_Sides', 'Irish_Oak_Both_Sides', 'Smooth_Anthracite_Grey_White',
                     'Agate_Grey_White']
    if 'upvc' in c:
        selected_colour = None
    else:
        selected_colour = next((field for colour, field in zip(colours, colour_fields) if colour in c), None)
    # --- Glass type ---
    if 'obscure' in c:
        selected_glass = 'Obscure'
    else:
        selected_glass = 'Clear'
    # --- Energy rating ---
    if 'a++ triple glazed' in c:
        selected_energy = 'A++ Triple Glazed'
    elif 'a+ rated energy upgrade' in c:
        selected_energy = 'A+ Rated Energy Upgrade'
    else:
        selected_energy = 'Standard A Rated'
    # --- Checkboxes ---
    toughened_glass = True if 'toughened glass' in c else None
    laminated_glass = True if 'laminated glass' in c else None
    fit_pack = True if 'fit pack' in c else None
    # --- Select (quantity) ---
    trickle_vents = 'Not Required'
    trickle_vents_match = re.search(r'(\d+)\s*trickle vents|trickle vents\s*(\d+)|x(\d+)|(\d+)x|\((\d+)\)|\[(\d+)\]', c)
    if trickle_vents_match:
        qty = next(g for g in trickle_vents_match.groups() if g is not None)
        trickle_vents = qty if qty in ('1', '2') else 'Not Required'
    elif 'trickle vents' in c:
        return parse_order_from_comment(comment)
    # --- Build and return model ---
    return NagivationStepsModel(
        Frame_Width_mm=width,
        Frame_Height_mm=height,
        No=None,
        mm85_Stub=True if selected_cill == '85mm Stub' else None,
        Standard_mm150=True if selected_cill == 'Standard 150mm' else None,
        mm180=True if selected_cill == '180mm' else None,
        White=True if selected_colour == 'White' else None,
        Oak_Both_Sides=True if selected_colour == 'Oak Both Sides' else None,
        Oak_White=True if selected_colour == 'Oak/White' else None,
        Rosewood_Both_Sides=True if selected_colour == 'Rosewood Both Sides' else None,
        Rosewood_White=True if selected_colour == 'Rosewood/White' else None,
        Anthracite_Grey_Both_Sides=True if selected_colour == 'Anthracite Grey Both Sides' else None,
        Anthracite_Grey_White=True if selected_colour == 'Anthracite Grey/White' else None,
        Chartwell_White=True if selected_colour == 'Chartwell/White' else None,
        Cream_Both_Sides=True if selected_colour == 'Cream Both Sides' else None,
        Cream_White=True if selected_colour == 'Cream/White' else None,
        Black_Brown_Both_Sides=True if selected_colour == 'Black-Brown Both Sides' else None,
        Black_Brown_White=True if selected_colour == 'Black-Brown/White' else None,
        Whitegrain_Both_Sides=True if selected_colour == 'Whitegrain Both Sides' else None,
        Irish_Oak_Both_Sides=True if selected_colour == 'Irish Oak Both Sides' else None,
        Smooth_Anthracite_Grey_White=True if selected_colour == 'Smooth Anthracite Grey/White' else None,
        Agate_Grey_White=True if selected_colour == 'Agate Grey/White' else None,
        Clear=True if selected_glass == 'Clear' else None,
        Obscure=True if selected_glass == 'Obscure' else None,
        Standard_A_Rated=True if selected_energy == 'Standard A Rated' else None,
        A_Plus_Rated_Energy_Upgrade=True if selected_energy == 'A+ Rated Energy Upgrade' else None,
        A_Plus_Plus_Triple_Glazed=True if selected_energy == 'A++ Triple Glazed' else None,
        Toughened_Glass=toughened_glass,
        Laminated_Glass=laminated_glass,
        Trickle_Vents=trickle_vents,
        Fit_Pack=fit_pack,
    )


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

    model = parse_comment(comment)
    values = model.model_dump(by_alias=True)
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

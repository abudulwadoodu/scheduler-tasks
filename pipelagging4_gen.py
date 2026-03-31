import re
import time
import random

from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeoutError

# ---------------------------------------------------------------------------
# Module-level configuration
# ---------------------------------------------------------------------------

PRICE_XPATH = '//*[@id="maincontent"]/div[3]/div/div[1]/section[1]/div/div/div[2]/div[3]/div[2]/div/div/div[3]/span[2]/span'

STEPS = [
    {
        "label": "Insulation to Suit Pipe Size",
        "xpath": "//select[@id='attribute186']",
        "type": "",
        "tag": "select",
    },
    {
        "label": "Insulation Thickness",
        "xpath": "//select[@id='attribute185']",
        "type": "",
        "tag": "select",
    },
]


# ---------------------------------------------------------------------------
# Comment parser
# ---------------------------------------------------------------------------

def parse_comment(comment: str, labels: list) -> dict:
    """
    Parse a comment like 'Armaflex 13mm Class O Insulation Tube 12mm Dia'
    into a dict keyed by label, with the correct <select> option value.

    Pipe Size options  (id=attribute186): 6,10,12,15,20,22,28,35,42,48,54,60,67,76,80,89,93,108,114
    Thickness options  (id=attribute185): 6,9,13,19,25,32
    """

    PIPE_SIZE_OPTIONS = {
        "6": "122",  "10": "123", "12": "124", "15": "125",
        "20": "127", "22": "128", "28": "129", "35": "130",
        "42": "131", "48": "164", "54": "132", "60": "133",
        "67": "134", "76": "135", "80": "136", "89": "137",
        "93": "138", "108": "139", "114": "140",
    }

    THICKNESS_OPTIONS = {
        "6": "116", "9": "165", "13": "118",
        "19": "119", "25": "120", "32": "121",
    }

    c = comment.lower()

    tokens  = re.findall(r"(\d+)\s*(mm|inch|\")?", c)
    numbers = [t[0] for t in tokens if t[0]]

    pipe_size = None
    thickness = None

    # Keyword-first: explicit diameter / pipe-size context
    dia_match = re.search(r"(\d+)\s*mm\s*(dia|od|pipe|bore)", c)
    if dia_match:
        pipe_size = dia_match.group(1)

    # Keyword-first: explicit thickness context
    thick_match = re.search(r"(\d+)\s*mm\s*(thick|wall|insulation|class)", c)
    if thick_match:
        thickness = thick_match.group(1)

    # Fallback: positional + plausibility filtering
    if thickness is None or pipe_size is None:
        thickness_candidates = [n for n in numbers if n in THICKNESS_OPTIONS]
        pipe_candidates      = [n for n in numbers if n in PIPE_SIZE_OPTIONS]

        if thickness is None and thickness_candidates:
            thickness = thickness_candidates[0]
        if pipe_size is None:
            remaining = [n for n in pipe_candidates if n != thickness]
            if remaining:
                pipe_size = remaining[0]

    pipe_value      = PIPE_SIZE_OPTIONS.get(pipe_size, "")
    thickness_value = THICKNESS_OPTIONS.get(thickness, "")

    result = {}
    for label in labels:
        if label == "Insulation to Suit Pipe Size":
            result[label] = pipe_value
        elif label == "Insulation Thickness":
            result[label] = thickness_value
        else:
            result[label] = ""

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _smart_locator(page, step, timeout=5000):
    """
    Return a clickable locator for the element described by *step*.
    Handles hidden inputs by finding the associated visible label or icon.
    """
    base = page.locator(f"xpath={step['xpath']}")

    try:
        base.wait_for(state="attached", timeout=2000)
    except Exception:
        return None

    if base.is_visible():
        return base

    element_id = base.get_attribute("id")

    if element_id:
        # Primary: u-check-icon div inside label[for=id]
        icon_div = page.locator(f"label[for='{element_id}'] div[class*='u-check-icon']")
        if icon_div.count() > 0:
            return icon_div.first

        # Fallback: plain label[for=id]
        label_for = page.locator(f"label[for='{element_id}']")
        if label_for.count() > 0:
            return label_for.first

    # Ancestor label → try icon div first
    ancestor_label = page.locator(f"xpath={step['xpath']}/ancestor::label")
    if ancestor_label.count() > 0:
        ancestor_icon = ancestor_label.first.locator("div[class*='u-check-icon']")
        if ancestor_icon.count() > 0:
            return ancestor_icon.first
        return ancestor_label.first

    # Label by visible text
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

    # Clickable wrapper fallback
    wrapper = page.locator(
        f"xpath={step['xpath']}/ancestor::*[self::div or self::span][1]"
    )
    if wrapper.count() > 0:
        return wrapper.first

    return base


def _xpath_to_css_for_select(xpath: str) -> str:
    """Convert //tag[@id='foo'] style XPath to CSS selector #foo."""
    m = re.match(r"^//\w*\[@id=['\"]([^'\"]+)['\"]\]$", xpath.strip())
    if m:
        return f"#{m.group(1)}"
    return xpath


def _select_option_partial(page, xpath: str, target: str) -> bool:
    """
    Select a <select> option using fuzzy / partial matching.
    Tries 3 strategies in order; returns True on success, False if no match.
    """
    css            = _xpath_to_css_for_select(xpath)
    target_stripped = target.strip()

    try:
        options = page.query_selector_all(f"{css} option")
    except Exception:
        options = []

    if not options:
        options = page.locator(f"xpath={xpath}").locator("option").all()

    boundary_pattern = re.compile(
        r"(?<!\d)" + re.escape(target_stripped) + r"(?!\d)",
        re.IGNORECASE,
    )

    for opt in options:
        raw_value    = opt.get_attribute("value") or ""
        visible_text = opt.inner_text().strip()

        # Strategy 1 – leading number exact match on value attribute
        leading = re.match(r"^(\d+(?:\.\d+)?)", raw_value)
        if leading and leading.group(1) == target_stripped:
            page.select_option(f"xpath={xpath}", value=raw_value)
            return True

        # Strategy 2 – word-boundary match on visible text
        if boundary_pattern.search(visible_text):
            page.select_option(f"xpath={xpath}", value=raw_value)
            return True

        # Strategy 3 – word-boundary match on raw value attribute
        if boundary_pattern.search(raw_value):
            page.select_option(f"xpath={xpath}", value=raw_value)
            return True

    # No match – dump options for debugging
    print(f"[DEBUG] No option matched '{target_stripped}' in <select> {xpath}. Available options:")
    for opt in options:
        print(f"  text={opt.inner_text().strip()!r}  value={opt.get_attribute('value')!r}")

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
    """
    Navigate to *url*, interact with the form described by STEPS using values
    derived from *comment*, then extract and return the price at *price_xpath*.
    """

    labels    = [step["label"] for step in STEPS]
    value_map = parse_comment(comment, labels)

    def _random_delay():
        time.sleep(random.uniform(0.5, 1.5))

    with sync_playwright() as playwright:
        browser = None
        try:
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

            # Block images / fonts / media to speed up page load
            context.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in {"image", "font", "media"}
                else route.continue_(),
            )

            page = context.new_page()

            # Navigate – domcontentloaded first, fall back to load
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            except PlaywrightTimeoutError:
                print("[WARN] domcontentloaded timed out – retrying with wait_until='load'")
                page.goto(url, wait_until="load", timeout=timeout)

            # Allow JS frameworks (Alpine.js, Vue, React) to hydrate
            time.sleep(2)

            # ------------------------------------------------------------------
            # Capture old price before interactions (for change detection)
            # ------------------------------------------------------------------
            old_price = None
            try:
                price_el = page.locator(f"xpath={price_xpath}").first
                price_el.wait_for(state="attached", timeout=3_000)
                old_price = price_el.inner_text().strip()
            except Exception:
                pass

            # ------------------------------------------------------------------
            # Execute steps
            # ------------------------------------------------------------------
            for idx, step in enumerate(STEPS):
                label = step.get("label")
                xpath = step.get("xpath")
                tag   = step.get("tag", "").lower()
                stype = step.get("type", "").lower()

                if not label or not xpath:
                    raise ValueError(
                        f"Step {idx} is missing 'label' or 'xpath': {step}"
                    )

                value = value_map.get(label)

                # Skip steps with no resolved value
                if value is None or value == "":
                    continue

                # ---- SELECT / DROPDOWN ----
                if tag == "select":
                    for attempt in range(3):
                        try:
                            locator = page.locator(f"xpath={xpath}").first
                            locator.wait_for(state="attached", timeout=timeout)
                            locator.scroll_into_view_if_needed()
                            matched = _select_option_partial(page, xpath, str(value))
                            if not matched:
                                raise RuntimeError(
                                    f"Step {idx} (select_dropdown): no option matched "
                                    f"target '{value}' in {xpath}"
                                )
                            break  # success
                        except RuntimeError:
                            raise  # no match – do not retry
                        except Exception as exc:
                            if attempt == 2:
                                raise RuntimeError(
                                    f"Step {idx} (select_dropdown) failed after 3 attempts "
                                    f"on {xpath}: {exc}"
                                ) from exc
                            time.sleep(1)

                # ---- INPUT: TEXT ----
                elif tag == "input" and stype == "text":
                    try:
                        locator = _smart_locator(page, step, timeout)
                        if locator is None:
                            raise RuntimeError(
                                f"Step {idx} (text input): element not found at {xpath}"
                            )
                        locator.scroll_into_view_if_needed()
                        locator.triple_click()
                        locator.type(str(value))
                    except PlaywrightTimeoutError as exc:
                        raise RuntimeError(
                            f"Step {idx} (text input) timed out on {xpath}"
                        ) from exc

                # ---- INPUT: RADIO ----
                elif tag == "input" and stype == "radio":
                    if value != "check":
                        continue
                    try:
                        locator = _smart_locator(page, step, timeout)
                        if locator is None:
                            raise RuntimeError(
                                f"Step {idx} (radio): element not found at {xpath}"
                            )
                        locator.scroll_into_view_if_needed()
                        locator.click()
                    except PlaywrightTimeoutError as exc:
                        raise RuntimeError(
                            f"Step {idx} (radio) timed out on {xpath}"
                        ) from exc

                # ---- INPUT: CHECKBOX ----
                elif tag == "input" and stype == "checkbox":
                    if value != "check":
                        continue
                    try:
                        locator = _smart_locator(page, step, timeout)
                        if locator is None:
                            raise RuntimeError(
                                f"Step {idx} (checkbox): element not found at {xpath}"
                            )
                        locator.scroll_into_view_if_needed()
                        # Only click if not already checked
                        base = page.locator(f"xpath={xpath}").first
                        try:
                            if not base.is_checked():
                                locator.click()
                        except Exception:
                            locator.click()
                    except PlaywrightTimeoutError as exc:
                        raise RuntimeError(
                            f"Step {idx} (checkbox) timed out on {xpath}"
                        ) from exc

                else:
                    raise ValueError(
                        f"Step {idx}: unknown tag/type combination "
                        f"tag={tag!r} type={stype!r}. "
                        f"Valid combinations: select/(any), input/text, "
                        f"input/radio, input/checkbox"
                    )

                _random_delay()

            # ------------------------------------------------------------------
            # Wait for price to change (stale-price guard)
            # ------------------------------------------------------------------
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
                    pass  # price may be unchanged – extraction will validate

            # ------------------------------------------------------------------
            # Extract price
            # ------------------------------------------------------------------
            try:
                price_locator = page.locator(f"xpath={price_xpath}").first
                price_locator.wait_for(state="attached", timeout=timeout)
            except PlaywrightTimeoutError as exc:
                raise TimeoutError(
                    f"Price element not found for XPath: {price_xpath}"
                ) from exc

            try:
                expect(price_locator).not_to_be_empty(timeout=timeout)
            except (PlaywrightTimeoutError, AssertionError) as exc:
                raise TimeoutError(
                    f"Price element found but empty for XPath: {price_xpath}"
                ) from exc

            raw_price     = price_locator.inner_text().strip()
            cleaned_price = re.sub(r"[€£¥₹,]", "", raw_price).strip()
            price = price_locator.inner_text().strip()
            price = re.sub(r"[^\d.]", "", price)
            print(f"Extracted price: {price} → cleaned: {cleaned_price}")

            # ------------------------------------------------------------------
            # Optional screenshot
            # ------------------------------------------------------------------
            if screenshot_path:
                page.screenshot(path=screenshot_path, full_page=True)
                print(f"Screenshot saved: {screenshot_path}")

            return cleaned_price

        finally:
            if browser:
                browser.close()


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
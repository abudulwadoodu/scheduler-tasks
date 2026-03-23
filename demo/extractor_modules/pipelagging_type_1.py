from playwright.sync_api import sync_playwright
import re
import json


def extract_dimensions_type1(text: str):
    dim = re.findall(r'\d+', text)
    if len(dim) < 2:
        raise ValueError("Could not extract diameter and thickness")
    return dim[0], dim[1]


def clean_price(price_text: str):
    match = re.search(r"[\d.]+", price_text)
    return match.group(0) if match else None


def wait_for_options_to_load(page, selector: str, timeout_ms: int = 30000):
    """Wait until a <select> has more than just the placeholder option."""
    page.wait_for_function(
        f"""() => {{
            const el = document.querySelector('{selector}');
            return el && el.options.length > 1;
        }}""",
        timeout=timeout_ms,
    )


def select_option_by_value_contains(page, selector: str, target: str) -> bool:
    """
    Select the first <option> whose text contains `target`.
    Returns True if a match was found and selected.
    """
    options = page.query_selector_all(f"{selector} option")
    for option in options:
        text = option.inner_text().strip()
        if target in text:
            value = option.get_attribute("value")
            page.select_option(selector, value=value)
            return True
    return False


def scrape_price(url: str, description: str, comment: str):
    diameter, thickness = extract_dimensions_type1(description)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto(url, timeout=120000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)  # let JS initialise dropdowns

        # ---------------------
        # Select Thickness
        # ---------------------
        wait_for_options_to_load(page, "#attribute187")
        matched = select_option_by_value_contains(page, "#attribute187", thickness)
        if not matched:
            print(f"[WARN] Thickness '{thickness}' not found in #attribute187")

        # Wait for the page to react (price/stock update, dependent dropdown reload)
        page.wait_for_timeout(1500)

        # ---------------------
        # Select Diameter
        # ---------------------
        # After selecting thickness, diameter options may reload — wait for them
        wait_for_options_to_load(page, "#attribute188")
        matched = select_option_by_value_contains(page, "#attribute188", diameter)
        if not matched:
            print(f"[WARN] Diameter '{diameter}' not found in #attribute188")

        # ---------------------
        # Wait for price update
        # ---------------------
        # Wait for any loading indicator to disappear first (common pattern)
        try:
            page.wait_for_selector(".loading, .ajax-loading", state="hidden", timeout=3000)
        except Exception:
            pass  # no loading overlay present — carry on

        price_selector = "div.price-excl-taxinline-block span.price"
        page.wait_for_selector(price_selector, timeout=10000)

        # Extra stability wait: poll until the price text stops changing
        def price_is_stable() -> str | None:
            el = page.query_selector(price_selector)
            return el.inner_text().strip() if el else None

        first_read = price_is_stable()
        page.wait_for_timeout(800)
        second_read = price_is_stable()

        # If price is still animating, wait a bit longer
        if first_read != second_read:
            page.wait_for_timeout(1500)

        price_text = price_is_stable()
        price = clean_price(price_text) if price_text else None

        browser.close()

        return {"extracted_price": price}


if __name__ == "__main__":
    url = "https://www.pipelagging.com/pipe-insulation/rockwool-rocklap-1m-foil-backed-pipe-insulation-lagging"
    description = "15 x 25mm H&V Lag Foil Covered"
    command = "Ap/Mar 24 updates ce increases all in 1m lengths"

    result = scrape_price(url, description, command)
    print(json.dumps(result))
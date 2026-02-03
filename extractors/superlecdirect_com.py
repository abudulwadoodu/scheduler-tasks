from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import re


# ---------------------------
# Helpers
# ---------------------------

def extract_size(description: str) -> str:
    """
    Extract size like:
    - 40x25mm
    - 40 x 25mm
    - 20mm
    """
    if not description:
        raise ValueError("Description required to extract size")

    match = re.search(r"(\d+)\s*[xX]\s*(\d+)mm", description)
    if match:
        return f"{match.group(1)}x{match.group(2)}mm"

    match = re.search(r"\b\d+mm\b", description)
    if match:
        return match.group(0)

    raise ValueError(f"No size found in description: {description}")


# ---------------------------
# Core Extractor
# ---------------------------

def extract(url: str, description: str | None = None) -> dict:
    """
    Extract a single product page from superlecdirect
    """

    print(f"[superdirect extractor] Extracting: {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context()
        page = context.new_page()

        try:
            # Navigate
            page.goto(url, timeout=60000, wait_until="domcontentloaded")

            # Optional: size selection (if required later)
            if description:
                _ = extract_size(description)
                # ⚠️ Currently no select_option used, but ready if needed

            # ---------------------------
            # WAIT FOR PRICE
            # ---------------------------
            price_xpath = (
                '//div[@class="sl_pd_active_price" and @id="ex_vat"]//span[1]'
            )

            price_el = page.wait_for_selector(
                f"xpath={price_xpath}",
                timeout=30000
            )

            price = price_el.inner_text().strip()

            if not price:
                raise LookupError("Price element found but value empty")

            return {
                "url": url,
                "price": None,
                "price_inc_vat": None,
                "price_excl_vat": price,
                "unit_price": None,
                "error": "",
            }

        except PlaywrightTimeout:
            page.screenshot(path="superdirect_timeout.png")
            raise LookupError("Price element did not load in time")

        finally:
            browser.close()

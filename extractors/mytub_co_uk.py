
import random
import time
from playwright.sync_api import sync_playwright

def random_delay(min_seconds=1, max_seconds=3):
    time.sleep(random.uniform(min_seconds, max_seconds))

def extract(url: str, description: str | None = None) -> dict:
    """Extract a single product page from mytub.co.uk"""

    print(f"[mytub extractor] Extracting: {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate to page
        page.goto(url, timeout=60000, wait_until="domcontentloaded")

        # ---------------------------
        # REQUIRED CONTAINER
        # ---------------------------
        container = page.locator('div[itemprop="offers"]')
        if not container.count():
            container = page.locator("img[alt='price']").locator("xpath=ancestor::div")

        # 🚨 If still not found → raise error so retry logic kicks in
        if not container.count():
            browser.close()
            raise ValueError("Required pricing container not found on page")

        # ---------------------------
        # EXTRACT PRICES
        # ---------------------------
        alt_prices = {}
        img_tags = container.locator("img[alt]")

        for i in range(img_tags.count()):
            img = img_tags.nth(i)
            alt = img.get_attribute("alt")
            font = img.locator("xpath=following-sibling::font[1]")

            if font.count() > 0:
                price = font.inner_text().strip()
                if alt:
                    alt_prices[alt.lower()] = price

        browser.close()

        if not alt_prices:
            raise ValueError("Price elements found but values missing")

        return {
            "url": url,
            "price": alt_prices.get("price"),
            "price_inc_vat": alt_prices.get("inc vat"),
            "price_excl_vat": alt_prices.get("excl vat"),
            "error": "",
        }

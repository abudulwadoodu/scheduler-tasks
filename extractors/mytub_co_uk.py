import random
import time
from playwright.sync_api import sync_playwright
import os, psutil

def log_memory(label):
    process = psutil.Process(os.getpid())
    
    # Include all child processes (Chromium, renderer, etc.)
    total = process.memory_info().rss
    children = process.children(recursive=True)
    for child in children:
        try:
            total += child.memory_info().rss
        except psutil.NoSuchProcess:
            pass  # process may have already closed
    
    total_mb = total / 1024 / 1024
    child_count = len(children)
    print(f"[{label}] Memory: {total_mb:.1f} MB (python + {child_count} child processes)")

    
def random_delay(min_seconds=1, max_seconds=3):
    time.sleep(random.uniform(min_seconds, max_seconds))

def extract(url: str, description: str | None = None) -> dict:
    """Extract a single product page from mytub.co.uk"""

    print(f"[mytub extractor] Extracting: {url}")

    log_memory("1. Before playwright")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        log_memory("2. After browser launch")

        page = browser.new_page()
        log_memory("3. After new page")

        # Navigate to page
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        log_memory("4. After page load  ← PEAK")  # this is your key number

        # ---------------------------
        # REQUIRED CONTAINER
        # ---------------------------
        container = page.locator('div[itemprop="offers"]')
        if not container.count():
            container = page.locator("img[alt='price']").locator("xpath=ancestor::div")

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

        log_memory("5. After extraction")

        browser.close()
        log_memory("6. After browser close  ← should drop back down")

        if not alt_prices:
            raise ValueError("Price elements found but values missing")

        return {
            "url": url,
            "price": alt_prices.get("price"),
            "price_inc_vat": alt_prices.get("inc vat"),
            "price_excl_vat": alt_prices.get("excl vat"),
            "error": "",
        }

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

XPATHS = {
    "container": "//div[@id='FetchProductShowPrice-react-component']",
    "price": ".//p[@data-testid='vat-price-main']",
    "price_inc_vat": ".//p[@data-testid='vat-price-secondary']",
}

def extract(url: str) -> dict:
    print(f"[cef extractor] Extracting: {url}")

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

            # ✅ WAIT for pricing container (React render complete)
            container = page.wait_for_selector(
                f"xpath={XPATHS['container']}",
                timeout=30000
            )

            # Scoped locators (more reliable)
            price_el = container.locator(f"xpath={XPATHS['price']}")
            price_inc_vat_el = container.locator(f"xpath={XPATHS['price_inc_vat']}")

            # Final validation
            if not price_el.count() or not price_inc_vat_el.count():
                raise ValueError("Price elements missing inside container")

            price = price_el.inner_text().strip()
            price_inc_vat = price_inc_vat_el.inner_text().strip()

            return {
                "url": url,
                "price": price,
                "price_inc_vat": price_inc_vat,
                "price_excl_vat": None,
                "error": "",
            }

        except PlaywrightTimeout:
            # 🔍 Debug help if it still fails
            page.screenshot(path="cef_timeout.png")
            raise ValueError("Pricing container did not load in time")

        finally:
            browser.close()

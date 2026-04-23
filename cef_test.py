from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import Stealth
import os, psutil, time

XPATHS = {
    "container": "//div[@id='FetchProductShowPrice-react-component']",
    "price": ".//p[@data-testid='vat-price-main']",
    "price_inc_vat": ".//p[@data-testid='vat-price-secondary']",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def log_resources(label, interval=0.5):
    process = psutil.Process(os.getpid())
    all_processes = [process] + process.children(recursive=True)

    total_cpu = 0
    total_mem = 0
    for p in all_processes:
        try:
            total_cpu += p.cpu_percent(interval=interval)
            total_mem += p.memory_info().rss
        except psutil.NoSuchProcess:
            pass

    total_cores = psutil.cpu_count()
    mem_mb = total_mem / 1024 / 1024

    print(
        f"[{label}] "
        f"CPU: {total_cpu:.1f}% | "
        f"Cores used: {total_cpu/100:.2f} | "
        f"Memory: {mem_mb:.1f} MB"
    )


def diagnose_page(page, label="diagnosis"):
    """Dump page state to help debug block/captcha issues"""
    print(f"\n--- PAGE DIAGNOSIS [{label}] ---")
    print(f"Title   : {page.title()}")
    print(f"URL     : {page.url}")
    print(f"Content : {page.content()[:800]}")
    print(f"--------------------------------\n")
    page.screenshot(path=f"cef_{label}.png")
    print(f"Screenshot saved: cef_{label}.png")


# ─────────────────────────────────────────────
# MAIN EXTRACTOR
# ─────────────────────────────────────────────

def extract(url: str) -> dict:
    print(f"\n[cef extractor] Extracting: {url}")

    log_resources("1. Before playwright")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )
        log_resources("2. After browser launch")

        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800},
            locale="en-GB",
            timezone_id="Europe/London",
        )

        # Apply stealth to context
        stealth = Stealth()
        stealth.apply_stealth_sync(context)

        page = context.new_page()
        log_resources("3. After new page + stealth")

        try:
            # ── NAVIGATION ──────────────────────────────
            start = time.time()
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            log_resources("4. After page load")

            # Diagnose immediately after load
            diagnose_page(page, label="after_load")

            # ── WAIT FOR REACT COMPONENT ─────────────────
            page.wait_for_load_state("networkidle", timeout=30000)
            log_resources("5. After networkidle  ← React render peak")

            container = page.wait_for_selector(
                f"xpath={XPATHS['container']}",
                timeout=60000
            )
            log_resources("6. After React container found")

            # ── EXTRACT PRICES ───────────────────────────
            price_el = container.locator(f"xpath={XPATHS['price']}")
            price_inc_vat_el = container.locator(f"xpath={XPATHS['price_inc_vat']}")

            if not price_el.count() or not price_inc_vat_el.count():
                diagnose_page(page, label="missing_elements")
                raise ValueError("Price elements missing inside container")

            price = price_el.inner_text().strip()
            price_inc_vat = price_inc_vat_el.inner_text().strip()
            log_resources("7. After extraction")

            elapsed = time.time() - start
            print(f"[cef extractor] Done in {elapsed:.1f}s | price={price} | inc_vat={price_inc_vat}")

            return {
                "url": url,
                "price": price,
                "price_inc_vat": price_inc_vat,
                "price_excl_vat": None,
                "error": "",
            }

        except PlaywrightTimeout as e:
            print(f"[cef extractor] TIMEOUT: {e}")
            diagnose_page(page, label="timeout")
            raise ValueError(f"Timeout waiting for pricing container: {e}")

        except Exception as e:
            print(f"[cef extractor] ERROR: {e}")
            diagnose_page(page, label="error")
            raise

        finally:
            browser.close()
            log_resources("8. After browser close")


# ─────────────────────────────────────────────
# TEST RUNNER
# ─────────────────────────────────────────────

if __name__ == "__main__":
    test_url = "https://www.cef.co.uk/catalogue/products/4586595-115-to-240v-ac-flashing-xenon-beacon-ip65-green"

    try:
        result = extract(test_url)
        print("\n✅ Result:")
        for k, v in result.items():
            print(f"  {k}: {v}")
    except ValueError as e:
        print(f"\n❌ Extraction failed: {e}")
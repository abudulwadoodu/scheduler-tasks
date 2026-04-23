# # xfrom playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# # XPATHS = {
# #     "container": "//div[@id='FetchProductShowPrice-react-component']",
# #     "price": ".//p[@data-testid='vat-price-main']",
# #     "price_inc_vat": ".//p[@data-testid='vat-price-secondary']",
# # }

# # def extract(url: str) -> dict:
# #     print(f"[cef extractor] Extracting: {url}")

# #     with sync_playwright() as p:
# #         browser = p.chromium.launch(
# #             headless=True,
# #             args=["--disable-blink-features=AutomationControlled"]
# #         )
# #         context = browser.new_context()
# #         page = context.new_page()

# #         try:
# #             # Navigate
# #             page.goto(url, timeout=60000, wait_until="domcontentloaded")

# #             # ✅ WAIT for pricing container (React render complete)
# #             container = page.wait_for_selector(
# #                 f"xpath={XPATHS['container']}",
# #                 timeout=30000
# #             )

# #             # Scoped locators (more reliable)
# #             price_el = container.locator(f"xpath={XPATHS['price']}")
# #             price_inc_vat_el = container.locator(f"xpath={XPATHS['price_inc_vat']}")

# #             # Final validation
# #             if not price_el.count() or not price_inc_vat_el.count():
# #                 raise ValueError("Price elements missing inside container")

# #             price = price_el.inner_text().strip()
# #             price_inc_vat = price_inc_vat_el.inner_text().strip()

# #             return {
# #                 "url": url,
# #                 "price": price,
# #                 "price_inc_vat": price_inc_vat,
# #                 "price_excl_vat": None,
# #                 "error": "",
# #             }

# #         except PlaywrightTimeout:
# #             # 🔍 Debug help if it still fails
# #             page.screenshot(path="cef_timeout.png")
# #             raise ValueError("Pricing container did not load in time")

# #         finally:
# #             browser.close()
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import os, psutil

XPATHS = {
    "container": "//div[@id='FetchProductShowPrice-react-component']",
    "price": ".//p[@data-testid='vat-price-main']",
    "price_inc_vat": ".//p[@data-testid='vat-price-secondary']",
}

# def log_memory(label):
#     process = psutil.Process(os.getpid())
#     total = process.memory_info().rss
#     children = process.children(recursive=True)
#     for child in children:
#         try:
#             total += child.memory_info().rss
#         except psutil.NoSuchProcess:
#             pass
#     total_mb = total / 1024 / 1024
#     print(f"[{label}] Memory: {total_mb:.1f} MB (python + {len(children)} child processes)")


import os, psutil, time

# def log_cpu(label, interval=0.5):
#     process = psutil.Process(os.getpid())
    
#     # Measure CPU across all child processes
#     all_processes = [process] + process.children(recursive=True)
    
#     total_cpu = 0
#     for p in all_processes:
#         try:
#             total_cpu += p.cpu_percent(interval=interval)
#         except psutil.NoSuchProcess:
#             pass
    
#     mem = sum(
#         p.memory_info().rss for p in all_processes
#         if not isinstance(p, psutil.NoSuchProcess)
#     ) / 1024 / 1024

#     print(f"[{label}] CPU: {total_cpu:.1f}% | Memory: {mem:.1f} MB")

def log_cpu(label, interval=0.5):
    process = psutil.Process(os.getpid())
    all_processes = [process] + process.children(recursive=True)

    total_cpu = 0
    for p in all_processes:
        try:
            total_cpu += p.cpu_percent(interval=interval)
        except psutil.NoSuchProcess:
            pass

    total_cores = psutil.cpu_count()                    # e.g. 8 cores
    normalized = total_cpu / total_cores                # % of total machine CPU

    print(f"[{label}] CPU: {total_cpu:.1f}% (single-core scale) "
          f"| {normalized:.1f}% (of {total_cores} cores) "
          f"| Cores used: {total_cpu/100:.2f}")

def extract(url: str) -> dict:
    print(f"[cef extractor] Extracting: {url}")

    log_cpu("1. Before playwright")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        log_cpu("2. After browser launch")

        context = browser.new_context()
        page = context.new_page()
        log_cpu("3. After new page")

        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            log_cpu("4. After page load")

            # ✅ WAIT for pricing container (React render complete)
            container = page.wait_for_selector(
                f"xpath={XPATHS['container']}",
                timeout=30000
            )
            log_cpu("5. After React container loaded  ← PEAK (JS rendered)")

            # Scoped locators
            price_el = container.locator(f"xpath={XPATHS['price']}")
            price_inc_vat_el = container.locator(f"xpath={XPATHS['price_inc_vat']}")

            if not price_el.count() or not price_inc_vat_el.count():
                raise ValueError("Price elements missing inside container")

            price = price_el.inner_text().strip()
            price_inc_vat = price_inc_vat_el.inner_text().strip()
            log_cpu("6. After extraction")

            return {
                "url": url,
                "price": price,
                "price_inc_vat": price_inc_vat,
                "price_excl_vat": None,
                "error": "",
            }

        except PlaywrightTimeout:
            page.screenshot(path="cef_timeout.png")
            raise ValueError("Pricing container did not load in time")

        finally:
            browser.close()
            log_cpu("7. After browser close")

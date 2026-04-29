import random
import pandas as pd
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Semaphore
from playwright.sync_api import sync_playwright


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


def get_stealth_context(browser):
    context = browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": random.randint(1280, 1920), "height": random.randint(720, 1080)},
        locale="en-US",
        timezone_id="America/New_York",
        java_script_enabled=True,
        has_touch=False,
        is_mobile=False,
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "DNT": "1",
        }
    )

    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        window.chrome = { runtime: {} };
    """)

    return context


def scrape_url(url: str, semaphore: Semaphore) -> str:
    with semaphore:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                    ]
                )
                context = get_stealth_context(browser)
                page = context.new_page()

                page.wait_for_timeout(random.randint(500, 1500))
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(random.randint(1000, 3000))

                html = page.content()
                browser.close()
                return html
        except Exception as e:
            return f"ERROR: {e}"


def scrape_excel(df: pd.DataFrame, file_path: str, url_col: str = "URL") -> pd.DataFrame:
    path = Path(file_path)

    semaphore = Semaphore(5)
    results = {}

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(scrape_url, row[url_col], semaphore): idx
            for idx, row in df.iterrows()
        }

        for future in as_completed(futures):
            idx = futures[future]
            results[idx] = future.result()

    df = df.copy()
    df["html_source"] = df.index.map(results)

    
    return df


if __name__ == "__main__":
    file_path = input("Excel file path: ").strip()
    source = input("Filter by Source: ").strip()

    df = pd.read_excel(file_path)

    filtered_df = df[df["Source\n"] == source].reset_index(drop=True)
    print(f"{len(filtered_df)} rows found for source '{source}'")

    df =scrape_excel(filtered_df, file_path)

    path = Path(file_path)
    output_path = path.parent / f"{source}_scraped{path.suffix}"

    df.to_excel(output_path, index=False)

    print(f"Saved to {output_path}")
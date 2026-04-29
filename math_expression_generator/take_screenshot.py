import os
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def accept_cookies_if_present(page, timeout_ms: int = 5000) -> bool:
    try:
        page.click("#CybotCookiebotDialogBodyLevelButtonAccept", timeout=timeout_ms)
        return True
    except Exception:
        try:
            page.get_by_role("button", name="Allow all cookies").click(timeout=timeout_ms)
            return True
        except Exception:
            return False


def capture_screenshot(
    url: str,
    output_dir: str = "screenshots",
    filename: str = None,
    timeout_ms: int = 30000,
) -> str | None:
    os.makedirs(output_dir, exist_ok=True)

    if filename is None:
        safe_name = url.replace("://", "_").replace("/", "_").replace("?", "_")[:100]
        filename = f"{safe_name}.png"

    img_path = os.path.join(output_dir, filename)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
            locale="en-GB",
            extra_http_headers={
                "Accept-Language": "en-GB,en;q=0.9",
                "Upgrade-Insecure-Requests": "1",
            },
        )
        page = context.new_page()
        try:
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            accepted = accept_cookies_if_present(page)
            if accepted:
                print(f"  [INFO] Cookies accepted for {url}")
            page.wait_for_timeout(1000)
            page.screenshot(path=img_path, full_page=True)

        except PlaywrightTimeoutError:
            print(f"  [TIMEOUT] {url}")
            img_path = None
        except Exception as e:
            print(f"  [ERROR] {url} -> {e}")
            img_path = None
        finally:
            page.close()
            browser.close()

    return img_path


def capture_screenshots_for_dataframe(
    df: pd.DataFrame,
    url_column: str = "URL",
    screenshot_dir: str = "screenshots",
    timeout_ms: int = 30000,
) -> pd.DataFrame:
    """
    Takes a DataFrame, captures a screenshot for each URL, and returns
    the DataFrame with an added 'img_path' column.

    Args:
        df:             Input DataFrame containing a URL column.
        url_column:     Name of the column containing URLs.
        screenshot_dir: Directory to save screenshots into.
        timeout_ms:     Navigation timeout per page in milliseconds.

    Returns:
        DataFrame with a new 'img_path' column.
    """
    df = df.copy()
    img_paths = []
    total = len(df)

    for i, (idx, row) in enumerate(df.iterrows(), start=1):
        url = row[url_column]
        print(f"[{i}/{total}] Capturing: {url}")

        if pd.isna(url) or str(url).strip() == "":
            print(f"  [SKIP] Empty URL at row {idx}")
            img_paths.append(None)
            continue

        path = capture_screenshot(
            url=str(url).strip(),
            output_dir=screenshot_dir,
            timeout_ms=timeout_ms,
        )
        img_paths.append(path)

    df["img_path"] = img_paths
    return df

if __name__ == "__main__":
    INPUT_EXCEL = input("Enter path to input Excel file [../dataset/datasetv2.xlsx]: ").strip()
    INPUT_EXCEL = INPUT_EXCEL or "../dataset/datasetv2.xlsx"

    URL_COLUMN = input("Enter URL column name [URL]: ").strip()
    URL_COLUMN = URL_COLUMN or "URL"

    OUTPUT_DIR = "dataset"

    if not os.path.exists(INPUT_EXCEL):
        print(f"[ERROR] File not found: {INPUT_EXCEL}")
        exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    data = pd.read_excel(INPUT_EXCEL)

    SOURCE_COLUMN = "Source\n"  # fixed column name

    if SOURCE_COLUMN not in data.columns:
        print(f"[ERROR] Column 'Source\\n' not found. Available columns: {list(data.columns)}")
        exit(1)

    # Show available sources and let user pick one
    unique_sources = data[SOURCE_COLUMN].dropna().unique()
    print(f"\nAvailable sources: {list(unique_sources)}")
    SOURCE_FILTER = input("Enter source name to filter by: ").strip()

    if SOURCE_FILTER not in unique_sources:
        print(f"[ERROR] Source '{SOURCE_FILTER}' not found. Available: {list(unique_sources)}")
        exit(1)

    source_df = data[data[SOURCE_COLUMN] == SOURCE_FILTER].reset_index(drop=True)
    print(f"\nProcessing source: {SOURCE_FILTER} ({len(source_df)} rows)")

    safe_source = SOURCE_FILTER.replace(" ", "_").replace("/", "_")
    screenshot_subdir = os.path.join("screenshots", safe_source)

    result_df = capture_screenshots_for_dataframe(
        df=source_df,
        url_column=URL_COLUMN,
        screenshot_dir=screenshot_subdir,
    )

    output_path = os.path.join(OUTPUT_DIR, f"{safe_source}_with_img_path.xlsx")
    result_df.to_excel(output_path, index=False)
    print(f"\nSaved → {output_path}")
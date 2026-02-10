import os
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def accept_cookies_if_present(page, timeout_ms: int = 5000) -> bool:
    """
    Attempts to accept cookie consent if a Cookiebot banner is present.
    Safe to call on every page.
    """
    try:
        # Preferred: exact Cookiebot button ID
        page.click("#CybotCookiebotDialogBodyLevelButtonAccept", timeout=timeout_ms)
        return True
    except Exception:
        try:
            # Fallback: button text (more general)
            page.get_by_role("button", name="Allow all cookies").click(timeout=timeout_ms)
            return True
        except Exception:
            # No cookie banner present
            return False


def capture_screenshots(
    df: pd.DataFrame,
    url_column: str = "URL",
    output_dir: str = "screenshots",
    timeout_ms: int = 30000,
) -> pd.DataFrame:
    """
    Capture full-page screenshots for URLs in the dataframe.
    """
    if url_column not in df.columns:
        raise ValueError(f"Column '{url_column}' not found in dataframe")

    os.makedirs(output_dir, exist_ok=True)
    img_paths = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
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

        for idx, row in df.iterrows():
            url = row[url_column]
            img_path = None
            page = context.new_page()

            try:
                page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)  # allow lazy content to render

                img_path = os.path.join(output_dir, f"case_{idx}.png")

                accepted = accept_cookies_if_present(page)
                if accepted:
                    print(f"[INFO] Cookies accepted for {url}")

                page.wait_for_timeout(1000)
                page.screenshot(path=img_path, full_page=True)

            except PlaywrightTimeoutError:
                print(f"[TIMEOUT] {url}")

            except Exception as e:
                print(f"[ERROR] {url} -> {e}")

            finally:
                page.close()

            img_paths.append(img_path)

        browser.close()

    df = df.copy()
    df["img_path"] = img_paths
    return df


if __name__ == "__main__":
    # Example usage
    df = pd.read_excel("./dataset/datasetv2.xlsx")
    result_df = capture_screenshots(df)
    result_df.to_excel("./dataset/datasetv3.xlsx", index=False)
    print(result_df)

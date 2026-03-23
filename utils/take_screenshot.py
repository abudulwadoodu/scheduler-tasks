import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def accept_cookies_if_present(page, timeout_ms: int = 5000) -> bool:
    """
    Attempts to accept cookie consent if a Cookiebot banner is present.
    Safe to call on every page.
    """
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
    """
    Capture a full-page screenshot for a single URL.

    Args:
        url:        The URL to screenshot.
        output_dir: Directory where the image will be saved.
        filename:   Optional filename (e.g. "my_page.png").
                    Defaults to a sanitised version of the URL.
        timeout_ms: Navigation timeout in milliseconds.

    Returns:
        The path to the saved screenshot, or None on failure.
    """
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
                print(f"[INFO] Cookies accepted for {url}")

            page.wait_for_timeout(1000)
            page.screenshot(path=img_path, full_page=True)

        except PlaywrightTimeoutError:
            print(f"[TIMEOUT] {url}")
            img_path = None

        except Exception as e:
            print(f"[ERROR] {url} -> {e}")
            img_path = None

        finally:
            page.close()
            browser.close()

    return img_path


if __name__ == "__main__":
    path = capture_screenshot("https://www.pipelagging.com/pipe-insulation/rockwool-rocklap-1m-foil-backed-pipe-insulation-lagging")
    print(f"Screenshot saved to: {path}")
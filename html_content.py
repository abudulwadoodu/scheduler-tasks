from playwright.sync_api import sync_playwright
from html_trimmer import trim_html

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://www.pipelagging.com/pipe-insulation/rockwool-rocklap-1m-foil-backed-pipe-insulation-lagging",
              wait_until="domcontentloaded")
    page.wait_for_timeout(2000)          # let JS hydrate

    raw_html = page.content()            # gets the live rendered DOM
    trimmed  = trim_html(raw_html, debug=True)

    print(trimmed[:3000])                # preview
    browser.close()
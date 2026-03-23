import asyncio
from playwright.async_api import async_playwright

async def scrape(url: str, role: str, name: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto(url, wait_until="networkidle")
        
        # Get ARIA snapshot
        snapshot = await page.locator("body").aria_snapshot()
        #snapshot = await page.accessibility.snapshot()
        print("=== ARIA Snapshot ===")
        print(snapshot)
        
        # Get element by role and name
        locator = page.get_by_role(role, name=name)
        count = await locator.count()
        print(f"\n=== Found {count} [{role}] element(s) with name '{name}' ===\n")
        
        for i in range(count):
            el = locator.nth(i)
            text = await el.inner_text()
            html = await el.evaluate("el => el.outerHTML")
            print(f"[{i+1}] Text: {text}")
            print(f"[{i+1}] HTML: {html}\n")
        
        await browser.close()

async def main():
    url  = input("URL  : ").strip()
    role = input("Role : ").strip()
    name = input("Name : ").strip()
    
    await scrape(url, role, name)

asyncio.run(main())
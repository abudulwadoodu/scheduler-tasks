import asyncio
from playwright.async_api import async_playwright

async def get_aria_snapshot(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print(f"Navigating to: {url}")
        await page.goto(url, wait_until="networkidle")
        
        # Get ARIA snapshot in native YAML format
        snapshot = await page.locator("body").aria_snapshot()
        
        await browser.close()
        return snapshot

async def main():
    url = input("Enter the URL: ").strip()
    
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    print("\nFetching ARIA snapshot...\n")
    snapshot = await get_aria_snapshot(url)
    
    if snapshot:
        print("=== ARIA Snapshot (YAML) ===\n")
        print(snapshot)
        
        # Save to file
        with open("aria_snapshot.yaml", "w", encoding="utf-8") as f:
            f.write(snapshot)
        print("\n✅ Snapshot saved to aria_snapshot.yaml")
    else:
        print("❌ Failed to get ARIA snapshot.")

asyncio.run(main())
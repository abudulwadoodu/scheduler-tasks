import asyncio
import yaml
from playwright.async_api import async_playwright

async def get_html_by_role(url: str, role: str, name: str = None):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto(url, wait_until="networkidle")
        
        # Step 1: Get ARIA snapshot
        snapshot_yaml = await page.locator("body").aria_snapshot()
        print("=== ARIA Snapshot ===\n")
        print(snapshot_yaml)
        
        # Step 2: Parse YAML to find matching nodes
        snapshot = yaml.safe_load(snapshot_yaml)
        matches = find_by_role(snapshot, role, name)
        
        print(f"\n=== Found {len(matches)} '{role}' element(s) ===\n")
        
        # Step 3: Locate each match in the page and get its HTML
        results = []
        for match in matches:
            match_name = match.get("name", "")
            
            # Build locator based on role and optional name
            if match_name:
                locator = page.get_by_role(role, name=match_name)
            else:
                locator = page.get_by_role(role)
            
            count = await locator.count()
            for i in range(count):
                el = locator.nth(i)
                outer_html = await el.evaluate("el => el.outerHTML")
                inner_html = await el.evaluate("el => el.innerHTML")
                
                result = {
                    "role": role,
                    "name": match_name,
                    "outer_html": outer_html,
                    "inner_html": inner_html,
                }
                results.append(result)
                
                print(f"[{role}] name='{match_name}'")
                print(f"Outer HTML:\n{outer_html}\n")
        
        await browser.close()
        return results


def find_by_role(node, target_role: str, target_name: str = None):
    """Recursively search YAML snapshot for nodes matching role (and optionally name)."""
    matches = []
    
    if isinstance(node, dict):
        role = node.get("role", "")
        name = node.get("name", "")
        
        role_match = role.lower() == target_role.lower()
        name_match = (target_name is None) or (target_name.lower() in name.lower())
        
        if role_match and name_match:
            matches.append(node)
        
        for child in node.get("children", []):
            matches.extend(find_by_role(child, target_role, target_name))
    
    elif isinstance(node, list):
        for item in node:
            matches.extend(find_by_role(item, target_role, target_name))
    
    return matches


async def main():
    url = input("Enter URL: ").strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    role = input("Enter role to find (e.g. textbox, button, link, heading): ").strip()
    name = input("Enter name filter (or press Enter to get all): ").strip() or None
    
    await get_html_by_role(url, role, name)


asyncio.run(main())


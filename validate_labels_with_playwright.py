"""
Validate that elements from a labels JSON file exist on a web page using Playwright.
Usage: python validate_labels_with_playwright.py <labels_json> <web_url>
"""
import sys
import json
from typing import Dict, Any, List
from playwright.sync_api import sync_playwright


def load_labels(json_path: str) -> Dict[str, Any]:
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def try_find_element(page, item: Dict[str, Any]):
    """
    Attempts to locate an element on the given page using various selectors
    derived from the item dictionary (such as id, name, label, tag, type,
    and group_label). Returns a tuple of the first matching selector and
    True if found, or a list of all tried selectors and False if not found.
    """
    selectors = []
    # Try id
    if item.get('id'):
        selectors.append(f"#{item['id']}")
    # Try name
    if item.get('name'):
        selectors.append(f"[name='{item['name']}']")
    # Try label text (for inputs)
    if item.get('label'):
        selectors.append(f"input[aria-label='{item['label']}']")
        selectors.append(f"input[placeholder='{item['label']}']")
        selectors.append(f"label:has-text('{item['label']}')")
    # Try tag/type
    if item.get('tag') and item.get('type'):
        selectors.append(f"{item['tag']}[type='{item['type']}']")
    elif item.get('tag'):
        selectors.append(f"{item['tag']}")
    # Try group_label as a section
    if item.get('group_label'):
        selectors.append(f"section:has-text('{item['group_label']}')")

    matched_selectors = []
    matched_html = []
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                try:
                    outer_html = el.evaluate("el => el.outerHTML")
                except Exception:
                    outer_html = None
                matched_selectors.append(sel)
                matched_html.append(outer_html)
        except Exception:
            continue
    if matched_selectors:
        return matched_selectors, True, matched_html
    return selectors, False, None


def main():
    if len(sys.argv) != 3:
        print("Usage: python validate_labels_with_playwright.py <labels_json> <web_url>")
        sys.exit(1)
    labels_path, url = sys.argv[1], sys.argv[2]
    data = load_labels(labels_path)
    inputs = data.get('inputs', [])
    report: List[Dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        page.wait_for_load_state('networkidle')
        for item in inputs:
            selectors, found, outer_html = try_find_element(page, item)
            report.append({
                'label': item.get('label'),
                'id': item.get('id'),
                'name': item.get('name'),
                'selectors_tried': selectors,
                'found': found,
                'outer_html': outer_html
            })
        browser.close()

    found_count = sum(1 for r in report if r['found'])
    print(f"\nValidation Report: {found_count}/{len(report)} elements found.\n")
    for r in report:
        status = 'FOUND' if r['found'] else 'NOT FOUND'
        if r['found']:
            print(f"Label: {r['label']}, id: {r['id']}, name: {r['name']} => {status}")
            print(f"  Selectors matched: {r['selectors_tried']}")
            if isinstance(r['outer_html'], list):
                for i, html in enumerate(r['outer_html']):
                    if html:
                        print(f"    Outer HTML [{i+1}]: {html[:500]}{'...' if len(html) > 500 else ''}")
            elif r['outer_html']:
                print(f"  Outer HTML: {r['outer_html'][:500]}{'...' if len(r['outer_html']) > 500 else ''}")
        else:
            print(f"Label: {r['label']}, id: {r['id']}, name: {r['name']} => {status}")
            print(f"  Selectors tried: {r['selectors_tried']}")

    # Export report as JSON file with timestamp
    import datetime
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    export_filename = f"report_{timestamp}.json"
    with open(export_filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nReport exported to {export_filename}\n")

if __name__ == "__main__":
    main()

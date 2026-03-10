import os
import json
import re
from bs4 import BeautifulSoup

# Import the functions from crawler_experiment.py
from crawler_experiment import extract_product_data, find_price_in_json_config

def test_extraction():
    # 1. Test using the archived HTML
    archive_path = r"c:\Users\Wadood\Projects\Test\Python Tests\Scheduler Tasks\html_archive\pipe-insulation_rockwool-rocklap-1m-foil-backed-pipe-insulation-lagging.html"
    
    if not os.path.exists(archive_path):
        print(f"Archive not found at {archive_path}")
        return

    with open(archive_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Test Case 1: 15 x 25mm
    desc = "15 x 25mm H&V Lag Foil Covered"
    print(f"\nTesting Description: {desc}")
    result = extract_product_data(html_content, "http://test.url", desc, "")
    print(json.dumps(result, indent=4))

    # Test Case 2: 22 x 25mm
    desc = "22 x 25mm H&V Lag Foil Covered"
    print(f"\nTesting Description: {desc}")
    result = extract_product_data(html_content, "http://test.url", desc, "")
    print(json.dumps(result, indent=4))

if __name__ == "__main__":
    test_extraction()

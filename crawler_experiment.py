import os
import time
import json
import httpx
import logging
import re
import asyncio
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# Configure Logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("crawl_experiment.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
HTML_ARCHIVE_DIR = "html_archive"
INPUT_EXCEL = "input_urls.xlsx"
OUTPUT_EXCEL = "output_prices.xlsx"
DEFAULT_DELAY = 1.5  # 1-2 seconds delay
MAX_WORKERS = 5

def ensure_dirs():
    if not os.path.exists(HTML_ARCHIVE_DIR):
        os.makedirs(HTML_ARCHIVE_DIR)
        logger.info(f"Created directory: {HTML_ARCHIVE_DIR}")

def load_from_excel(filepath):
    if not os.path.exists(filepath):
        logger.error(f"Excel file not found: {filepath}")
        return []
    try:
        df = pd.read_excel(filepath)
        # Ensure mandatory columns exist
        if 'URL' not in df.columns or 'Description' not in df.columns:
            logger.error("Excel must contain 'URL' and 'Description' columns.")
            return []
        
        # Replace NaN with empty string for comments
        if 'comments' not in df.columns:
            df['comments'] = ""
        else:
            df['comments'] = df['comments'].fillna("")
            
        data = df.to_dict('records')
        logger.info(f"Loaded {len(data)} rows from {filepath}")
        return data
    except Exception as e:
        logger.error(f"Error reading Excel: {e}")
        return []

def save_to_excel(results, output_path):
    try:
        df = pd.DataFrame(results)
        df.to_excel(output_path, index=False)
        logger.info(f"Results saved to {output_path}")
    except Exception as e:
        logger.error(f"Error saving results to Excel: {e}")

def save_html(url, html_content):
    parsed = urlparse(url)
    # Create a safe filename from the path
    filename = parsed.path.strip("/").replace("/", "_") or "index"
    if not filename.endswith(".html"):
        filename += ".html"
    
    filepath = os.path.join(HTML_ARCHIVE_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    return filepath

def find_price_near_text(soup, target_text):
    """
    Finds a price pattern near a specific text element.
    """
    # Look for exact text or partial match
    elements = soup.find_all(string=re.compile(re.escape(target_text), re.I))
    
    # regex for price like £1,234.56 or £12.34
    price_regex = re.compile(r'£\s?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)')

    for element in elements:
        parent = element.parent
        # Look in the same row if in a table
        row = parent.find_parent('tr')
        if row:
            row_text = row.get_text(separator=' ', strip=True)
            match = price_regex.search(row_text)
            if match:
                return match.group(0), "description_match (table row)"
        
        # Look in parent element's text
        parent_text = parent.get_text(separator=' ', strip=True)
        match = price_regex.search(parent_text)
        if match:
            return match.group(0), "description_match (parent)"
            
        # Look in siblings or next elements
        for sibling in parent.find_next_siblings():
            sib_text = sibling.get_text(separator=' ', strip=True)
            match = price_regex.search(sib_text)
            if match:
                return match.group(0), "description_match (sibling)"
                
    return None, None

def find_price_in_json_config(html_content, target_description):
    """
    Extracts and parses the initConfigurableOptions JSON blob from the HTML.
    Matches the target_description against variant attributes to find the price.
    """
    # 1. Locate the start of the JSON configuration
    # Pattern looks for initConfigurableOptions('PID', {
    start_match = re.search(r'initConfigurableOptions\s*\(\s*\'\d+\'\s*,\s*(\{)', html_content)
    if not start_match:
        return None, None

    # Use brace balancing to find the end of the JSON object
    start_index = start_match.start(1)
    brace_count = 0
    end_index = -1
    for i in range(start_index, len(html_content)):
        if html_content[i] == '{':
            brace_count += 1
        elif html_content[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                end_index = i + 1
                break
    
    if end_index == -1:
        logger.debug("Could not find matching closing brace for JSON config")
        return None, None

    config_str = html_content[start_index:end_index]

    try:
        # Basic cleanup for potential JS object notation vs strict JSON
        # 1. Quote unquoted keys (only if they aren't already quoted)
        # Matches a key that starts with a word char and is followed by a colon, 
        # but is NOT preceded by a quote.
        config_str = re.sub(r'(?<!["\'])(\b\w+\b)\s*:', r'"\1":', config_str)
        # 2. Remove trailing commas before closing braces/brackets
        config_str = re.sub(r',(\s*[\]\}])', r'\1', config_str)
        
        config = json.loads(config_str)
        
        attributes = config.get("attributes", {})
        option_prices = config.get("optionPrices", {})
        index = config.get("index", {})

        # 2. Extract numeric parts (e.g., "15", "25") from target_description
        desc_parts = re.findall(r'(\d+)', target_description.lower())
        if not desc_parts:
            logger.debug(f"No numeric parts found in description: {target_description}")
            return None, None

        logger.debug(f"Matching desc parts {desc_parts} against JSON variants")

        # 3. Match against index product IDs
        for product_id, attr_selections in index.items():
            attr_values = []
            for attr_id, option_id in attr_selections.items():
                attr_info = attributes.get(attr_id, {})
                for opt in attr_info.get("options", []):
                    if str(opt.get("id")) == str(option_id):
                        label = str(opt.get("label", "")).lower()
                        # Extract number from label (e.g., "15mm" -> "15")
                        label_num = re.search(r'(\d+)', label)
                        if label_num:
                            attr_values.append(label_num.group(1))
                        break
            
            # Check if all numbers from description are present in this variant's attributes
            if all(part in attr_values for part in desc_parts):
                price_data = option_prices.get(product_id, {})
                final_price = price_data.get("finalPrice", {}).get("amount")
                if final_price:
                    logger.info(f"Matched variant ID {product_id} for {target_description}")
                    return f"£{final_price:.2f}", "deep_variant_extraction (JSON config)"

    except Exception as e:
        logger.debug(f"JSON config parsing failed: {e}")
    
    return None, None

def extract_product_data(html_content, url, target_description, target_comment=""):
    """
    Extracts targeted product information based on description and comment.
    """
    # 0. Deep Strategy: JSON Config Match (Hyva/Magento)
    price, method = find_price_in_json_config(html_content, target_description)
    
    soup = None
    
    # 1. Fallback to Heuristics if JSON fails
    if not price:
        soup = BeautifulSoup(html_content, 'html.parser')
        price, method = find_price_near_text(soup, target_description)
    
    # 2. Fallback to Comment-based Logic (Selectors/Tables)
    if not price and target_comment:
        if soup is None:
            soup = BeautifulSoup(html_content, 'html.parser')
        
        comment = target_comment.lower()
        if "selector" in comment:
            parts = target_comment.split("selector")
            if len(parts) > 1:
                sel = parts[1].strip()
                tag = soup.select_one(sel)
                if tag:
                    price = tag.get_text(strip=True)
                    method = "comment_logic (selector)"
        
        if not price and "table" in comment:
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    if target_description.lower() in row.get_text().lower():
                        price_regex = re.compile(r'£\s?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)')
                        match = price_regex.search(row.get_text())
                        if match:
                            price = match.group(0)
                            method = "comment_logic (table scan)"
                            break
                if price: break

    # 3. Numeric Price Adjustments (e.g., "divide price x2m")
    if price and target_comment:
        if "divide" in target_comment.lower() and "x2m" in target_comment.lower():
            # Clean price string
            numeric_price = re.sub(r'[^\d.]', '', price)
            try:
                val = float(numeric_price) / 2.0
                # Preserve symbol if possible
                symbol = "£" if "£" in price else ""
                price = f"{symbol}{val:.2f}"
                method += " + price_division"
            except: pass

    return {
        "URL": url,
        "Description": target_description,
        "Extracted Price": price or "N/A",
        "Method": method or "failed",
        "Status": "found" if price else "not found"
    }

async def fetch_url(client, row):
    url = row['URL']
    description = row['Description']
    comment = row.get('comments', '')
    
    start_time = time.time()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }
    try:
        response = await client.get(url, headers=headers, timeout=15.0, follow_redirects=True)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            save_html(url, response.text)
            result_data = extract_product_data(response.text, url, description, comment)
            logger.info(f"Fetched {url} - Extracted: {result_data['Extracted Price']} via {result_data['Method']}")
            return {**row, **result_data}
        else:
            logger.error(f"Error status {response.status_code} for {url}")
            return {**row, "Extracted Price": "N/A", "Method": "failed (status code)", "Status": "error"}
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return {**row, "Extracted Price": "N/A", "Method": f"failed ({type(e).__name__})", "Status": "failed"}

async def run_experiment(all_data, sequential=True):
    import random
    results = []
    ensure_dirs()
    
    total = len(all_data)
    async with httpx.AsyncClient(http2=True) as client:
        for i, row in enumerate(all_data):
            print(f"\nProcessing {i+1}/{total}")
            print(f"URL: {row['URL']}")
            print(f"Description: {row['Description']}")
            
            res = await fetch_url(client, row)
            results.append(res)
            
            if sequential and i < total - 1:
                delay = random.uniform(2.0, 4.0)
                await asyncio.sleep(delay)
                
    return results

def print_summary(results):
    total = len(results)
    success = sum(1 for r in results if r.get("status") == "success")
    failed = total - success
    times = [r["duration"] for r in results if "duration" in r]
    avg_time = sum(times) / len(times) if times else 0
    
    print("\n" + "="*40)
    print("CRAWL EXPERIMENT SUMMARY")
    print("="*40)
    print(f"Total URLs processed: {total}")
    print(f"Successful fetches:   {success}")
    print(f"Failed fetches:       {failed}")
    print(f"Avg response time:    {avg_time:.2f}s")
    print("="*40)
    
    # Print sample extraction
    if results:
        active_results = [r for r in results if r.get("status") == "success"]
        if active_results:
            print("\nSample Extraction Result:")
            print(json.dumps(active_results[0]["data"], indent=2))

if __name__ == "__main__":
    
    # Check if input Excel exists
    if not os.path.exists(INPUT_EXCEL):
        print(f"Please create {INPUT_EXCEL} with columns: URL, Description, comments")
    else:
        input_data = load_from_excel(INPUT_EXCEL)
        if input_data:
            crawl_results = asyncio.run(run_experiment(input_data, sequential=True))
            save_to_excel(crawl_results, OUTPUT_EXCEL)
            print(f"\nFinished! Results saved to {OUTPUT_EXCEL}")
        else:
            print("No data found in Excel.")

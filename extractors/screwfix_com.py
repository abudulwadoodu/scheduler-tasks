from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright
import pandas as pd
import random
import time
import re

def extract_size(description: str) -> str:
    # First look for patterns like "40x25mm" or "40 x 25mm"
    match = re.search(r"(\d+)\s*[xX]\s*(\d+)mm", description)
    if match:
        return f"{match.group(1)}x{match.group(2)}mm"
    
    # Otherwise fallback to simple "20mm"
    match = re.search(r"\b\d+mm\b", description)
    if match:
        return match.group(0)

    # If nothing matched
    raise ValueError(f"No size found in description: {description}")




def get_price(page, description: str, wait_seconds: float = 3.0):
    # Wait until the product price section appears
    #page.wait_for_selector("//div[@data-qaid='pdp-price']", timeout=wait_seconds * 2000)
    time.sleep(2)  # Static wait to ensure all elements load properly
    # XPath for integer and decimal parts of the main price
    
    currency_symbol_xpath = '//div[@data-qaid="pdp-price"]//span[contains(@class,"ogtgsW")]'
    price_integer_xpath = "//div[@data-qaid='pdp-price']//span[contains(@class,'_U1S20')]"

    price_decimal_xpath = "//div[@data-qaid='pdp-price']//span[contains(@class,'xIIluZ')]"
    # Get integer and decimal parts if they exist
    integer_part_locator = page.locator(f"xpath={price_integer_xpath}")
    decimal_part_locator = page.locator(f"xpath={price_decimal_xpath}")
    currency_symbol_locator = page.locator(f"xpath={currency_symbol_xpath}")
    print(f"Integer part count: {integer_part_locator.count()}, Decimal part count: {decimal_part_locator.count()}")

    

    integer_part = integer_part_locator.nth(0).inner_text().strip() if integer_part_locator.count() > 0 else None
    decimal_part = decimal_part_locator.nth(0).inner_text().strip() if decimal_part_locator.count() > 0 else None
    currency = currency_symbol_locator.nth(0).inner_text().strip() if currency_symbol_locator.count() > 0 else None

    # Build full price if integer part exists
    full_price = f"{currency}{integer_part}{decimal_part}" if integer_part and decimal_part else integer_part

    # XPath for price per unit
    per_unit_xpath = "//span[@data-qaid='pdp-price-per-unit']"
    per_unit_locator = page.locator(f"xpath={per_unit_xpath}")
    per_unit_text = per_unit_locator.nth(0).inner_text().strip() if per_unit_locator.count() > 0 else None

    # Raise error only if BOTH main price and per unit are missing
    if not full_price and not per_unit_text:
        raise LookupError("No product price or per unit price found. Page structure may have changed.")

    print(f"Full Price: {full_price}, Per Unit: {per_unit_text}")
    
    return {
        "price": full_price,
        "per unit": per_unit_text.strip("()£") if per_unit_text else None
    }






from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

def scrape_product_data(row, max_retries: int = 2) -> dict:
    url = row['URL']
    code = row['Code']
    time.sleep(2 + random.uniform(30, 60))
    for attempt in range(1, max_retries + 1):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
                context = browser.new_context()
                page = context.new_page()
                page.goto(url, timeout=200000, wait_until="domcontentloaded")

                description = row['Description']
                alt_prices = get_price(page, description)

                return {
                    "Code": code,
                    "URL": url,
                    "extracted_price": alt_prices.get('price', 'N/A'),
                    "extracted_price_inc_VAT": alt_prices.get('inc vat', 'N/A'),
                    "extracted_price_excl_VAT": alt_prices.get('excl vat', 'N/A'),
                    "unit_price": alt_prices.get('per unit', 'N/A'),
                    "error": ""
                }
               
                   

        except ValueError as ve:
            # size not in description
            print(f"[Attempt {attempt}] Failed to scrape {url}: {ve}")
            return {**row, "error": f"ValueError: {ve}"}

        except LookupError as le:
            # element missing / page structure changed
            print(f"[Attempt {attempt}] Failed to scrape {url}: {le}")
            return {**row, "error": f"LookupError: {le}"}

        except PlaywrightTimeoutError as te:
            # network / load issue
            print(f"[Attempt {attempt}] Failed to scrape {url}: {te}")
            return {**row, "error": f"TimeoutError: {te}"}

        except Exception as e:
            # unexpected
            print(f"[Attempt {attempt}] Failed to scrape {url}: {e}")
            return {**row, "error": f"Exception: {e}"}
        
     

# Load the Excel file
file_path = './data/sample_all_screwfix.xlsx'
df = pd.read_excel(file_path)
df = df[['Code', 'URL', 'Description','Comments']]
#df = df[:10]
# Ensure only relevant columns are used
df = df[df['Code']=='BMM4018']
urls = df['URL'].astype(str).tolist()


# ThreadPool settings
MAX_WORKERS = 2  # Number of pages scraped at the same time
SAVE_INTERVAL = 5
results = []
start_time = time.time()

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(scrape_product_data, row): row for _, row in df.iterrows()}

    for i, future in enumerate(as_completed(futures), start=1):
        result = future.result()
        results.append(result)
        print("i : ", i)
        if i % SAVE_INTERVAL == 0 or i == len(df):
            out_df = pd.DataFrame(results)
            suffix = i // SAVE_INTERVAL if i % SAVE_INTERVAL == 0 else (i // SAVE_INTERVAL) + 1
            filename = f'sample_all_screwfix_scrapped{suffix}.xlsx'
            out_df.to_excel("newdata/" + filename, index=False)
            elapsed = time.time() - start_time
            print(f"Saved {filename}. Scraped {i} URLs. Time elapsed: {elapsed:.2f} seconds")

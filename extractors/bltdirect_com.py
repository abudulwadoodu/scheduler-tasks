# from playwright.async_api import async_playwright
# import re

# async def select_size_and_get_price(page, description: str):
#     # Extract size (e.g. "20mm") from description
#     match = re.search(r"\b\d+mm\b", description)
#     if not match:
#         raise ValueError(f"No size found in description: {description}")
    
#     size_value = match.group(0)

#     print(f"Extracted size value: {size_value}")

#     # Select the option
#     await page.select_option("#pa_size", value=size_value)
#     print(f"Selected size: {size_value}")

#     # Price locator (visible price)
#     price_locator = page.locator("p.price ins .woocommerce-Price-amount")

#     # Wait until price is visible
#     await price_locator.wait_for(state="visible", timeout=10000)

#     # Get the visible price text (like "£12.29")
#     visible_price = await price_locator.inner_text()

#     # Alternatively, read structured data-price attributes
#     price_data_locator = page.locator("p.price .woocommerce-price-data")
#     price_data = await price_data_locator.get_attribute("data-price-sale-inc-tax")

#     print(f"Visible price: {visible_price}")
#     print(f"Price (from data attribute): {price_data}")
#     return visible_price




# from concurrent.futures import ThreadPoolExecutor, as_completed
# from playwright.sync_api import sync_playwright
# import pandas as pd
# import random
# import time


# file_path = './data/sample_all_colglo.xlsx'
# df = pd.read_excel(file_path)
# urls = df['URL'].tolist()


# # 

# def scrape_product_data(row, max_retries: int = 2) -> dict:
#     url = row['URL']
#     code = row['Code']

#     for attempt in range(1, max_retries + 1):
#         try:
#             with sync_playwright() as p:
#                 browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
#                 context = browser.new_context()
#                 page = context.new_page()
#                 page.goto(url, timeout=200000, wait_until="domcontentloaded")

#                 description = row['Description'] #"20mm (3/4) MS Cap" 

#                 price_inc_vat_text = select_size_and_get_price(page, description)
              

#                 print(f"Price Inc VAT: {price_inc_vat_text}")                

#                 alt_prices = {
#                     "inc vat": price_inc_vat_text.strip()
#                 }
#                 browser.close()
#                 return {
#                     "Code": code,
#                     "URL": url,
#                     "extracted_price": alt_prices.get('price', 'N/A'),
#                     "extracted_price_inc_VAT": alt_prices.get('inc vat', 'N/A'),
#                     "extracted_price_excl_VAT": alt_prices.get('excl vat', 'N/A'),
#                     "error": ""
#                 }

#         except Exception as e:
#             print(f"[Attempt {attempt}] Failed to scrape {url}: {e}")
#             if attempt == max_retries:
#                 return {
#                     "Code": code,
#                     "URL": url,
#                     "extracted_price": "",
#                     "extracted_price_incl_VAT": "",
#                     "extracted_price_excl_VAT": "",
#                     "error": f"Failed after {max_retries} attempts: {str(e)}"
#                 }
#         time.sleep(2 + random.uniform(0, 2))


# # ThreadPool settings
# MAX_WORKERS = 5  # Number of pages scraped at the same time
# SAVE_INTERVAL = 30
# results = []
# start_time = time.time()

# with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
#     futures = {executor.submit(scrape_product_data, row): row for _, row in df.iterrows()}

#     for i, future in enumerate(as_completed(futures), start=1):
#         result = future.result()
#         results.append(result)

#         if i % SAVE_INTERVAL == 0 or i == len(df):
#             out_df = pd.DataFrame(results)
#             suffix = i // SAVE_INTERVAL if i % SAVE_INTERVAL == 0 else (i // SAVE_INTERVAL) + 1
#             filename = f'sample_all_colglo_scrapped{suffix}.xlsx'
#             out_df.to_excel("newdata/" + filename, index=False)
#             elapsed = time.time() - start_time
#             print(f"Saved {filename}. Scraped {i} URLs. Time elapsed: {elapsed:.2f} seconds")




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



# def get_price(page, description: str, wait_seconds: float = 3.0):
    

#     # Price (inc VAT)
#     inc_vat_locator = page.locator("div.price__inc_vat-container strong.price__inc_vat")
#     inc_vat_price = inc_vat_locator.inner_text().strip() if inc_vat_locator.count() > 0 else None

#     # Price (ex VAT)
#     ex_vat_locator = page.locator("div.js-vs-initial-ex-vat strong.js-price-ex-vat")
#     ex_vat_price = ex_vat_locator.inner_text().strip() if ex_vat_locator.count() > 0 else None

#     print(f"Inc VAT Price: {inc_vat_price}, Ex VAT Price: {ex_vat_price}")

#     if not inc_vat_price and not ex_vat_price:
#         raise LookupError("Neither inc VAT nor ex VAT price found.")

#     return {
#         "inc vat": inc_vat_price,
#         "excl vat": ex_vat_price
#     }

def get_price(page, description: str, wait_seconds: float = 3.0):
    # Wait for prices to be ready
   
    page.wait_for_selector("span.text-small:has-text('Inc. VAT')", timeout=wait_seconds * 1000)

    # Correct XPath for Inc VAT
    inc_vat_xpath = "//span[@class='text-small' and contains(text(),'Inc. VAT')]/following-sibling::span[@class='h5'][1]"
    inc_vat_locator = page.locator(f"xpath={inc_vat_xpath}")
    inc_vat_price = inc_vat_locator.nth(0).inner_text().strip() if inc_vat_locator.count() > 0 else None

    print(f"Inc VAT Price: {inc_vat_price}")
    # # XPath for Ex VAT
    # ex_vat_xpath = "//div[contains(@class,'js-vs-initial-ex-vat')]//strong[contains(@class,'js-price-ex-vat')]"
    # ex_vat_locator = page.locator(f"xpath={ex_vat_xpath}")
    # ex_vat_price = ex_vat_locator.inner_text().strip() if ex_vat_locator.count() > 0 else None

    if not inc_vat_price :
        raise LookupError("inc VAT not price found. Page structure may have changed.")

    return {
        "inc vat": inc_vat_price,
    }






from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

def scrape_product_data(row, max_retries: int = 2) -> dict:
    url = row['URL']
    code = row['Code']

    for attempt in range(1, max_retries + 1):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
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
file_path = './data/sample_all_bltdirectcom.xlsx'
df = pd.read_excel(file_path)
df = df[['Code', 'URL', 'Description','Comments']]

# Ensure only relevant columns are used
urls = df['URL'].astype(str).tolist()


# ThreadPool settings
MAX_WORKERS = 3  # Number of pages scraped at the same time
SAVE_INTERVAL = 30
results = []
start_time = time.time()

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(scrape_product_data, row): row for _, row in df.iterrows()}

    for i, future in enumerate(as_completed(futures), start=1):
        result = future.result()
        results.append(result)

        if i % SAVE_INTERVAL == 0 or i == len(df):
            out_df = pd.DataFrame(results)
            suffix = i // SAVE_INTERVAL if i % SAVE_INTERVAL == 0 else (i // SAVE_INTERVAL) + 1
            filename = f'sample_all_bltdirectcom_scrapped{suffix}.xlsx'
            out_df.to_excel("newdata/" + filename, index=False)
            elapsed = time.time() - start_time
            print(f"Saved {filename}. Scraped {i} URLs. Time elapsed: {elapsed:.2f} seconds")
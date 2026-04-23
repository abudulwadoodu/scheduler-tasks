from playwright.sync_api import sync_playwright
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright
import pandas as pd
import random
import time
import re
import time
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


import re

def extract_dimensions_type1(text: str) -> list[int]:
    """
    Extract all integer values from a given text.
    
    Args:
        text (str): Input string
    
    Returns:
        list[int]: List of integers found in the text
    """
    return [int(num) for num in re.findall(r'\d+', text)]

def extract_dimensions_type2(text: str) -> list[int]:
    """
    Extract all integer values from a given text.
    
    Args:
        text (str): Input string
    
    Returns:
        list[int]: List of integers found in the text
    """
    return [num for num in re.findall(r'\d+mm', text)]

import re
def extract_size(description: str) -> str:
    return


def get_price(page, desc,comment,Type) -> str:

    if Type == 1:
        dim = extract_dimensions_type1(desc)
        print(dim)
        diameter = str(dim[0])
        thickness = str(dim[1])

        time.sleep(5)

        options = page.query_selector_all('#attribute187 option')
    
        print("thickness : ",thickness)
        for option in options:
            text = option.inner_text().strip()
            if thickness in text:
                value = option.get_attribute('value')
                page.select_option('#attribute187', value)
                print(f"Selected thickness: {text}")
                break

        time.sleep(2)

        options = page.locator("#attribute188 option").all()
        print("diameter :",diameter )
        for option in options:
            option_text = option.text_content().strip()
            if diameter in option_text:
                value_attr = option.get_attribute("value")
                page.select_option("#attribute188", value=value_attr)
                print(f"Selected Diameter: {option_text}")
                break

       

        time.sleep(2)

        page.wait_for_selector('div.price-excl-taxinline-block')
    
        # Extract the price using the div class as a pointer
        price_element = page.query_selector('div.price-excl-taxinline-block span.price')
        price = price_element.inner_text().strip() if price_element else None
        
        print(f"Price : {price}")

        return {
        "excl vat": price,
        }
    
    elif Type == 4:
        print("type : ",Type)
        dim = extract_dimensions_type2(desc)
        print(dim)

        if Type == 2:
            diameter = str(dim[0])
            thickness = str(dim[1])
        else:
            thickness = str(dim[0])
            diameter = str(dim[1])

        time.sleep(5)

        options = page.locator("#attribute185 option").all()
        
        print("Thickness :",thickness)
        for option in options:
            option_text = option.text_content().strip()
            if thickness in option_text:
    
                value_attr = option.get_attribute("value")
                page.select_option("#attribute185", value=value_attr)
                print(f"Selected thickness: {option_text}")
                break

        time.sleep(5)


        #options = page.locator("#attribute186 option").all()
        options = page.query_selector_all('#attribute186 option')
        print("Diameter :",diameter)
        for option in options:
            option_text = option.text_content().strip()
            print("option : ",option_text)
            if diameter in option_text:

                value_attr = option.get_attribute("value")
                page.select_option("#attribute186", value=value_attr)
                print(f"Selected pipesize: {option_text}")
                break

        time.sleep(5)

        page.wait_for_selector('div.price-excl-taxinline-block')
        
            # Extract the price using the div class as a pointer
        price_element = page.query_selector('div.price-excl-taxinline-block span.price')
        price = price_element.inner_text().strip() if price_element else None
        
        print(f"Price for {diameter}mm: {price}")

        return {
        "excl vat": price,
        }
    


    elif Type == 2:

        print("type : ",Type)
        dim = extract_dimensions_type2(desc)
        print(dim)

        if Type == 2:
            diameter = str(dim[0])
            thickness = str(dim[1])
        else:
            thickness = str(dim[0])
            diameter = str(dim[1])

        time.sleep(3)


        #options = page.locator("#attribute186 option").all()
        options = page.query_selector_all('#attribute186 option')
        print("Diameter :",diameter)
        for option in options:
            option_text = option.text_content().strip()
            print("option : ",option_text)
            if diameter in option_text:

                value_attr = option.get_attribute("value")
                page.select_option("#attribute186", value=value_attr)
                print(f"Selected pipesize: {option_text}")
                break

        time.sleep(3)

        options = page.locator("#attribute185 option").all()
        
        print("Thickness :",thickness)
        for option in options:
            option_text = option.text_content().strip()
            if thickness in option_text:
    
                value_attr = option.get_attribute("value")
                page.select_option("#attribute185", value=value_attr)
                print(f"Selected thickness: {option_text}")
                break


        
        page.wait_for_selector('div.price-excl-taxinline-block')
        
            # Extract the price using the div class as a pointer
        price_element = page.query_selector('div.price-excl-taxinline-block span.price')
        price = price_element.inner_text().strip() if price_element else None
        
        print(f"Price for {diameter}mm: {price}")

        time.sleep(5)
        

        return {
        "excl vat": price,
        }
    
    elif Type == 3:
        time.sleep(3)
        price_element = page.locator("div.final-price-excl-tax span.price").nth(0)
    
    # Get the text content
        price = price_element.text_content()
        
        print("price : ",price)
        # Strip spaces and return
        return {
        "excl vat": price,
        }
        
    return {
        "excl vat": price,
    }



def scrape_product_data(row, max_retries: int = 3) -> dict:
    url = row['URL']
    code = row['Code']
    Type =  row['Type']
    comment =  row['Comments']
    desc = row['Description']
    time.sleep(random.uniform(2, 5))  # Initial random delay before starting

    for attempt in range(1, max_retries + 1):
        try:
            print("retry : ",attempt)
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
                context = browser.new_context()
                page = context.new_page()
                page.goto(url, timeout=200000, wait_until="domcontentloaded")

                product_code =  row['Supplier Code']
                print("TO URL : ", url)
                print("Code : ", product_code)
                alt_prices = get_price(page, desc,comment,Type)

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
            if attempt == max_retries:

                return {**row, "error": f"ValueError: {ve}"}

        except LookupError as le:
            # element missing / page structure changed
            print(f"[Attempt {attempt}] Failed to scrape {url}: {le}")
            if attempt == max_retries:

                return {**row, "error": f"LookupError: {le}"}

        except PlaywrightTimeoutError as te:
            # network / load issue
            print(f"[Attempt {attempt}] Failed to scrape {url}: {te}")
            if attempt == max_retries:

                return {**row, "error": f"TimeoutError: {te}"}

        except Exception as e:
            # unexpected
            print(f"[Attempt {attempt}] Failed to scrape {url}: {e}")
            if attempt == max_retries:
                return {**row, "error": f"Exception: {e}"}
        
        time.sleep(5 + random.uniform(6, 12))

# Load the Excel file
file_path = './data/sample_all_pipelagging.xlsx'
df = pd.read_excel(file_path)
df = df[df['Type'].isin([2])]
#df = df[:1]
urls = df['URL'].astype(str).tolist()


# ThreadPool settings
MAX_WORKERS = 5 # Number of pages scraped at the same time
SAVE_INTERVAL = 30
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
            filename = f'sample_all_pipelagging_scrapped{suffix}.xlsx'
            out_df.to_excel("newdata/" + filename, index=False)
            elapsed = time.time() - start_time
            print(f"Saved {filename}. Scraped {i} URLs. Time elapsed: {elapsed:.2f} seconds")


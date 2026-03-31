import pandas as pd
from justdooruk_gen_3 import scrape_price

test_data = pd.read_excel("./dataset/justdooruk_materials.xlsx")
test_data['text_input'] = test_data['Description'] + " " + test_data['Comments']


url = test_data.loc[0, 'URL']
comment = test_data.loc[0, 'text_input']    
PRICE_XPATH = '//span[contains(@class, "totalpricevisible")]'


def run_test(test_data : pd.DataFrame):
    for index, row in test_data.iterrows():
        url = row['URL']
        comment = row['text_input']
        price = scrape_price(
            url=url,
            comment=comment,
            price_xpath=PRICE_XPATH,
            headless=False,
            screenshot_path=f"price_screenshot_{index}.png",
            timeout=20000,
        )
        test_data.loc[index, 'Extracted_Price'] = price
        print(f"Extracted price for index {index}: {price}")

    print(test_data[['URL', 'text_input', 'Extracted_Price']])

if __name__ == "__main__":
    run_test(test_data[:1])
              

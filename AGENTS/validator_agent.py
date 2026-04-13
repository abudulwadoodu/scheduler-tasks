# validator_agent.py

from concurrent.futures import ThreadPoolExecutor
from price_input_validator import PriceInputValidator

def run_validator(labels_json_path: str, web_url: str, output_path: str = "results.json"):
    validator = PriceInputValidator()
    
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(
            validator.validate,
            labels_json_path=labels_json_path,
            web_url=web_url,
            output_path=output_path
        )
        return future.result()
# web_explorer_agent.py

import asyncio
from concurrent.futures import ThreadPoolExecutor
from playwright_input_labels_langchain import get_inputs

def run_explorer(URL: str):
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(get_inputs, URL)
        return future.result()
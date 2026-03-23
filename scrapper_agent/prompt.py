from string import Template
import json

def load_prompt(steps, price_xpath):

    with open("prompt.md", "r", encoding="utf-8") as f:
        template = Template(f.read())

    prompt = template.safe_substitute(
        steps=json.dumps(steps, indent=2),
        price_xpath=price_xpath
    )

    return prompt


steps = [
    {"action": "select_dropdown", "xpath": "//*[@id='attribute188']", "value": "15"},
    {"action": "select_dropdown", "xpath": "//*[@id='attribute187']", "value": "25"},
]

price_xpath = "//div[contains(@class,'final-price-excl-tax')]//span[contains(@class,'price text-base')]"


BASE_PROMPT = load_prompt(steps, price_xpath)


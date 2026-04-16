import sys
import json

from playwright_input_labels_langchain import get_inputs
from script_generator_agent import script_generator
from parser_generator_agent import parser_generator
from pydantic_model_generator_agent import model_generator
from web_explorer_agent import run_explorer
from validator_agent import run_validator



# extract html element (text)
def extract_elements(validated_inputs):
    elements = ""
    for elem in validated_inputs:
        elements = elements + elem['label']+"\n"+elem['outer_html']+'\n\n'
    return elements


    
# steps (List)
def get_steps(sample: dict) -> list[dict]:
    steps = []

    for elem in sample:
        tag       = elem['input_data'].get("tag", "input")
        elem_name = elem['input_data'].get("name", "")
        elem_type = elem['input_data'].get("type", "").lower()
        elem_label = elem['input_data'].get("label", "")
        xpath = elem.get('xpath')


        steps.append({"label": elem_label, "xpath": xpath, "type": elem_type, "tag": tag})

    return steps

# extract xpath
def extract_price_xpath(data: dict) -> str | None:
    """
    Extract price xpath with priority:
    1. price_without_tax
    2. price_with_tax
    3. base_price
    """
    priority = ['price_without_tax', 'price_with_tax', 'base_price']
    
    for key in priority:
        entry = data.get(key)
        if isinstance(entry, dict) and entry.get('xpath'):
            return entry['xpath']
    
    return None



def run_workflow(url,comment):
    # web explorer agent
    data = run_explorer(url)
    
    with open('input_jsons/output.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    # validator agent
    result = run_validator(
        labels_json_path="input_jsons/output.json",
        web_url=url,
        output_path="results.json"
    )

    validated_data = result.model_dump()
    validated_inputs = result.model_dump()['validated_inputs']

    steps = get_steps(validated_inputs)
    SAMPLE_HTML = extract_elements(validated_inputs)
    PRICE_XPATH = extract_price_xpath(validated_data['price_xpaths'])


    if steps != []:
        SAMPLE_MODEL = model_generator(SAMPLE_HTML, comment)
        PARSER = parser_generator(SAMPLE_MODEL, comment)
    else:
        SAMPLE_MODEL = ""
        PARSER = ""

    STEPS = str(steps) 

    # Generate script - Agent3
    script_generator(
            comment_parser_function=PARSER,
            steps=STEPS,
            price_xpath=PRICE_XPATH,
            pydantic_model = SAMPLE_MODEL,
            output_path="final_script.py",
    )


if __name__ == "__main__":
    url     = input("Enter URL: ")
    comment = input("comment : ")

    run_workflow(url,comment)
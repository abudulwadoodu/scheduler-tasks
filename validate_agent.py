import json
from typing import Optional
from pydantic import BaseModel



import base64
import json
import os
from typing import Optional, List
from pydantic import BaseModel
from openai import AzureOpenAI
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

class LabelData(BaseModel):
    label: str
    id: str
    name: str
    valid_selector: str
    identified_element: Optional[str] = None
    reason: str


class AzureOpenAiUIAgent:
    def __init__(self, api_key: str = None, api_base: str = None, api_version: str = None, model: str = None, temperature: float = None):
        # Load from .env if not provided, using .env variable names
        self.api_key = api_key or os.getenv("AZURE_API_KEY")
        self.api_base = api_base or os.getenv("AZURE_API_BASE")
        self.api_version = api_version or os.getenv("AZURE_API_VERSION")
        self.model = model or os.getenv("AZURE_API_MODEL", "gpt-4.1")
        self.temperature = temperature if temperature is not None else float(os.getenv("AZURE_API_TEMPERATURE", 0.1))
        self.client = AzureOpenAI(
            api_key=self.api_key,
            api_version=self.api_version,
            azure_endpoint=self.api_base
        )

    def _image_to_base64(self, image_path: str) -> str:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")

    def _build_prompt(self, input_json: dict) -> str:
        selectors = input_json.get("selectors_tried", [])
        htmls = input_json.get("outer_html", [])
        prompt = f"""
You are an expert UI agent. Given a screenshot of a web page and the following clues from a UI input extraction process, your job is to:
1. Decide which selector from the list is most likely to point to the correct UI input in the screenshot.
2. Use the provided HTML snippets (corresponding to each selector) to help you reason.
3. Identify (by description) what UI input element in the screenshot the selector points to, if possible.
4. Look for input elements (like dropdown, input fields, checkboxes etc) that are interactive and not labels.
5. Only return a selector as valid_selector if it is specific enough to uniquely identify a single element on the page. If all selectors are too generic (e.g., would match multiple elements or are ambiguous), set valid_selector to an empty string "" and explain in the reason field why no unique selector could be chosen.
6. Explain your reasoning.

Input JSON:
Label: {input_json.get('label')}
ID: {input_json.get('id')}
Name: {input_json.get('name')}
Selectors tried: {selectors}
HTML for selectors: {htmls}

Return a JSON object with:
    valid_selector: the best selector from selectors_tried (must be unique, or "" if none are unique)
    identified_element: a short description of the UI element in the screenshot (or null if not found)
    reason: a concise explanation of your reasoning
"""
        return prompt

    def run(self, input_json: dict, screenshot_path: str) -> LabelData:
        prompt = self._build_prompt(input_json)
        image_b64 = self._image_to_base64(screenshot_path)
        messages = [
            {"role": "system", "content": "You are a helpful UI verification assistant."},
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
            ]}
        ]
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=messages,
            max_tokens=512
        )
        content = response.choices[0].message.content
        try:
            result = json.loads(content)
        except Exception:
            # fallback: try to extract JSON from text
            import re
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                result = json.loads(match.group(0))
            else:
                raise ValueError("Could not parse LLM response as JSON")
        return LabelData(
            label=input_json.get("label", ""),
            id=input_json.get("id", ""),
            name=input_json.get("name", ""),
            valid_selector=result.get("valid_selector", ""),
            identified_element=result.get("identified_element"),
            reason=result.get("reason", "")
        )

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AzureOpenAi UI Agent for selector verification")
    parser.add_argument("input_json", help="Path to input JSON file")
    parser.add_argument("screenshot", help="Path to screenshot image file")
    parser.add_argument("--output", "-o", help="Path to output JSON file", default=None)
    args = parser.parse_args()

    with open(args.input_json, "r") as f:
        input_data = json.load(f)

    agent = AzureOpenAiUIAgent()

    # If input_data is a list, process each element; else, process as single object
    if isinstance(input_data, list):
        results = [agent.run(item, args.screenshot) for item in input_data]
        json_results = [r.model_dump() for r in results]
        for idx, res in enumerate(results):
            print(f"Result {idx+1}:")
            print(res.model_dump_json(indent=2))
        if args.output:
            with open(args.output, "w") as outf:
                json.dump(json_results, outf, indent=2)
    else:
        result = agent.run(input_data, args.screenshot)
        print(result.model_dump_json(indent=2))
        if args.output:
            with open(args.output, "w") as outf:
                json.dump(result.model_dump(), outf, indent=2)
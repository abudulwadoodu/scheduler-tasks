"""
Input validator using Playwright to verify JSON inputs against actual webpage.
"""
import json
import os
import os
from typing import List, Optional
from playwright.sync_api import sync_playwright, Page, Locator
from openai import AzureOpenAI, OpenAI
from .models import InputElement, LabelsJSON, LabelData
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
import dotenv

dotenv.load_dotenv()


class InputValidator:
    """Validates input elements from JSON against actual webpage."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        """Initialize the input validator with optional LLM credentials."""
        # self.llm_client = None
        # self.model = model
        
       
        self.llm_client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model or "gpt-4.1"
    
    def analyze_element_with_llm(self, outer_html: str, expected_label: str) -> str:
        """
        Use LLM to analyze the outer HTML and generate a description of the element.
        
        Args:
            outer_html: The outer HTML of the element
            expected_label: The expected label from the JSON
            
        Returns:
            Human-readable description of the element
        """
        if not self.llm_client:
            # Fallback to simple description if no LLM available
            return f"Element with expected label '{expected_label}'"
        
        try:
            system_prompt = """You are a UI/UX analyst. Analyze HTML elements and provide concise, descriptive observations about what they represent in the user interface.

Provide a 1-2 sentence description that:
1. Identifies the element type and purpose
2. Notes any visible labels, placeholders, or context
3. Describes its role in the UI (e.g., "allows user to input...", "displays...")

Be specific and factual based on the HTML structure."""
            
            user_prompt = f"""Analyze this HTML element and describe what it represents in the UI:

```html
{outer_html}
```

Expected label from data: "{expected_label}"

Provide a concise description of this element."""
            
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=200,
                temperature=0.1
            )
            
            description = response.choices[0].message.content.strip()
            return description
            
        except Exception as e:
            # Fallback on error
            return f"Element with expected label '{expected_label}' (LLM analysis failed: {str(e)})"
    
    def get_xpath(self, element: InputElement) -> str:
        """
        Generate XPath selector for an input element.
        
        Args:
            element: The input element to generate XPath for
            
        Returns:
            XPath string
        """
        tag = element.tag or "*"
        
        # Prefer ID (most specific)
        if element.id:
            return f'//*[@id="{element.id}"]'
        
        # Name + Type combination
        if element.name and element.type:
            return f'//{tag}[@name="{element.name}" and @type="{element.type}"]'
        elif element.name:
            return f'//{tag}[@name="{element.name}"]'
        
        # Class name
        if element.class_name:
            return f'//{tag}[contains(@class, "{element.class_name}")]'
        
        # Fallback to just tag
        return f'//{tag}'
    
    def validate_element(
        self,
        page: Page,
        element: InputElement
    ) -> LabelData:
        """
        Validate a single input element on the page.
        
        Args:
            page: Playwright page object
            element: Input element to validate
            
        Returns:
            LabelData with validation results
        """
        xpath = self.get_xpath(element)
        label_data = LabelData(
            label=element.label,
            xpath=xpath,
            input_data=element.model_dump()
        )
        
        try:
            # Try to locate the element
            locator = page.locator(f"xpath={xpath}")
            count = locator.count()
            
            if count == 0:
                label_data.verified = False
                label_data.reason = "Element not found on page with generated XPath"
                label_data.identified_element = f"Could not locate {element.tag} element"
            elif count > 1:
                label_data.verified = False
                label_data.reason = f"XPath matches {count} elements (ambiguous)"
                label_data.identified_element = f"Multiple {element.tag} elements matched"
            else:
                # Element found!
                label_data.verified = True
                
                # Get outer HTML
                outer_html = locator.evaluate("el => el.outerHTML")
                label_data.outer_html = outer_html
                
                # Use LLM to analyze and describe the element
                label_data.identified_element = self.analyze_element_with_llm(
                    outer_html=outer_html,
                    expected_label=element.label
                )
                label_data.reason = "Successfully located and verified on page"
                
        except Exception as e:
            label_data.verified = False
            label_data.reason = f"Error during validation: {str(e)}"
            label_data.identified_element = "Validation failed due to error"
        
        return label_data
    
    def validate_inputs(
        self,
        url: str,
        labels_json: LabelsJSON
    ) -> List[LabelData]:
        """
        Validate all input elements from JSON against the webpage.
        
        Args:
            url: The webpage URL
            labels_json: Parsed JSON with inputs to validate
            
        Returns:
            List of LabelData validation results
        """
        results = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            
            try:
                print(f"🌐 Loading {url}...")
                try:
                    page.goto(url, wait_until="networkidle", timeout=60000)
                except Exception as e:
                    print(f"[WARN] networkidle timed out, retrying with 'load' event: {e}")
                    page.goto(url, wait_until="load", timeout=60000)
                    page.wait_for_timeout(5000)  
                else:
                    page.wait_for_timeout(2000)  

                print(f"✅ Page loaded, validating {len(labels_json.inputs)} inputs...")

                for i, input_element in enumerate(labels_json.inputs, 1):
                    print(f"  [{i}/{len(labels_json.inputs)}] Validating: {input_element.label}")
                    label_data = self.validate_element(page, input_element)
                    results.append(label_data)
                    status = "✓" if label_data.verified else "✗"
                    print(f"    {status} {label_data.reason}")
                
            finally:
                browser.close()
        
        verified_count = sum(1 for r in results if r.verified)
        print(f"\n📊 Validation complete: {verified_count}/{len(results)} elements verified")
        
        return results

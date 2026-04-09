"""
Screenshot analyzer using GPT-4 Vision to identify price-relevant input components.
"""
import base64
import json
from typing import List
from playwright.sync_api import sync_playwright, Page
from openai import AzureOpenAI, OpenAI
from .models import IdentifiedComponent


class ScreenshotAnalyzer:
    """Analyzes webpage screenshots to identify price-relevant input components."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4.1-vision-preview"
    ):
        """Initialize the screenshot analyzer with Azure OpenAI credentials."""
        self.client = OpenAI(api_key=api_key)  # Use OpenAI client for GPT-4 Vision
        self.model = model
    
    def capture_screenshot(self, url: str) -> bytes:
        """
        Capture a full-page screenshot of the given URL.
        
        Args:
            url: The webpage URL to screenshot
            
        Returns:
            Screenshot as bytes
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            
            try:
                try:
                    page.goto(url, wait_until="networkidle", timeout=60000)
                except Exception as e:
                    print(f"[WARN] networkidle timed out, retrying with 'load' event: {e}")
                    page.goto(url, wait_until="load", timeout=60000)
                    page.wait_for_timeout(5000) 
                else:
                    page.wait_for_timeout(2000)
                # Take full page screenshot
                screenshot_bytes = page.screenshot(full_page=True)
                return screenshot_bytes
            finally:
                browser.close()
        
    
    def analyze_screenshot(self, screenshot_bytes: bytes) -> List[IdentifiedComponent]:
        """
        Analyze screenshot using GPT-4 Vision to identify price-relevant inputs.
        
        Args:
            screenshot_bytes: Screenshot image as bytes
            
        Returns:
            List of identified components
        """
        # Encode screenshot to base64
        base64_image = base64.b64encode(screenshot_bytes).decode('utf-8')
        
        # Create the vision prompt
        system_prompt = """You are an expert web scraping analyst. Your task is to identify ALL interactive input components on a webpage that could affect the final price of a product or service.

Look for:
- Text input fields (dimensions, quantities, custom text)
- Dropdown/select menus (options, materials, colors)
- Radio buttons (choices that may change price)
- Checkboxes (add-ons, extras, features)
- Sliders or number spinners
- Date pickers
- Any other interactive element that affects pricing

For EACH component, provide:
1. label: The visible label or text associated with it
2. type: The input type (text, select, radio, checkbox, slider, etc.)
3. description: Clear description of what it controls
4. price_relevance_reason: Why this affects the final price
5. group_context: The section/group it belongs to (if visible)

Be thorough - identify ALL inputs, even if they seem minor."""

        user_prompt = """Analyze this webpage screenshot and identify ALL input components that could affect the final price.

Return your response as a JSON array of objects with this structure:
[
  {
    "label": "Frame Width",
    "type": "text",
    "description": "Text input for entering frame width in millimeters",
    "price_relevance_reason": "Larger dimensions typically increase material cost and price",
    "group_context": "Dimensions section"
  }
]

Be comprehensive and identify every single price-relevant input on this page."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4096,
                temperature=0.1
            )
            
            # Parse the response
            content = response.choices[0].message.content
            
            # Extract JSON from response (may be wrapped in markdown)
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()
            
            # Parse JSON
            components_data = json.loads(json_str)
            
            # Convert to Pydantic models
            components = [IdentifiedComponent(**comp) for comp in components_data]
            
            return components
            
        except Exception as e:
            print(f"Error analyzing screenshot: {e}")
            raise
    
    def analyze_url(self, url: str) -> List[IdentifiedComponent]:
        """
        Complete workflow: capture screenshot and analyze it.
        
        Args:
            url: The webpage URL to analyze
            
        Returns:
            List of identified components
        """
        print(f"📸 Capturing screenshot of {url}...")
        screenshot_bytes = self.capture_screenshot(url)
        
        print(f"🔍 Analyzing screenshot with vision model...")
        components = self.analyze_screenshot(screenshot_bytes)
        
        print(f"✅ Identified {len(components)} price-relevant components")
        
        return components

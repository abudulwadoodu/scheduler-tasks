# Price Input Validator

A comprehensive system for validating price-relevant web form inputs using GPT-4 Vision and Playwright.

## Overview

This tool helps you:
1. 🔍 **Identify** all price-relevant input components from webpage screenshots using GPT-4 Vision
2. ✅ **Validate** JSON input configurations against actual webpages using Playwright
3. 📊 **Analyze gaps** between what's on the page and what's in your JSON config

## Features

- **Vision-based Analysis**: Uses GPT-4 Vision to automatically identify all interactive elements that affect pricing
- **XPath Validation**: Validates each JSON input against the live webpage using Playwright
- **Gap Detection**: Uses LLM-based fuzzy matching to find missing components
- **Comprehensive Reporting**: Detailed validation results with success/failure reasons
- **Pydantic Models**: Type-safe data structures throughout

## Installation

### Prerequisites

```bash
# Install Python dependencies
pip install playwright openai pydantic python-dotenv

# Install Playwright browsers
playwright install chromium
```

### Environment Setup

Create a `.env` file in your project root:

```env
AZURE_API_KEY=your_azure_openai_key
AZURE_API_BASE=https://your-resource.openai.azure.com/
AZURE_API_VERSION=2024-02-15-preview
AZURE_API_MODEL=gpt-4
```

## Usage

### Command Line

```bash
# Basic usage
python -m price_input_validator.main labels.json https://example.com/product

# With custom output file
python -m price_input_validator.main labels.json https://example.com/product results.json
```

### Python API

```python
from price_input_validator import PriceInputValidator

# Initialize validator
validator = PriceInputValidator()

# Run validation
result = validator.validate(
    labels_json_path="labels.json",
    web_url="https://example.com/product",
    output_path="results.json"
)

# Access results
print(f"Found {len(result.required_components)} components")
print(f"Verified {len([v for v in result.validated_inputs if v.verified])} inputs")
print(f"Missing {len(result.missing_components)} components")
```

### Individual Components

```python
from price_input_validator import ScreenshotAnalyzer, InputValidator, GapAnalyzer

# 1. Vision analysis only
analyzer = ScreenshotAnalyzer(
    api_key="...",
    api_base="...",
    api_version="..."
)
components = analyzer.analyze_url("https://example.com")

# 2. Input validation only
validator = InputValidator()
labels_json = LabelsJSON(**json_data)
validated = validator.validate_inputs(url, labels_json)

# 3. Gap analysis only
gap_analyzer = GapAnalyzer(...)
missing = gap_analyzer.find_missing_components(vision_components, validated_inputs)
```

## Input Format

Your `labels.json` should follow this structure:

```json
{
  "price": {
    "label": "115.00",
    "tag": "span",
    "class_name": "waspricevisible",
    "bbox": {
      "left": 366.1875,
      "top": 920.6875,
      "right": 409.234375,
      "bottom": 936.6875
    }
  },
  "inputs": [
    {
      "label": "Frame Width (mm)",
      "group_label": "Dimensions:",
      "tag": "input",
      "type": "text",
      "name": "framewidth",
      "id": "framewidth",
      "bbox": {
        "left": 576.0,
        "top": 540.65625,
        "right": 1179.0,
        "bottom": 574.15625
      },
      "is_price_relevant": true
    }
  ]
}
```

## Output Format

The validation results are saved as JSON:

```json
{
  "required_components": [
    {
      "label": "Frame Width",
      "type": "text",
      "description": "Text input for frame width",
      "price_relevance_reason": "Larger dimensions increase cost",
      "group_context": "Dimensions section"
    }
  ],
  "validated_inputs": [
    {
      "label": "Frame Width (mm)",
      "xpath": "//*[@id='framewidth']",
      "verified": true,
      "identified_element": "input element type='text', name='framewidth'",
      "reason": "Successfully located and verified on page"
    }
  ],
  "missing_components": [
    {
      "label": "Delivery Options",
      "type": "select",
      "description": "Dropdown for delivery method",
      "reason_missing": "Found on page but not in JSON"
    }
  ],
  "summary": {
    "total_vision_components": 15,
    "total_json_inputs": 12,
    "verified_inputs": 11,
    "failed_validations": 1,
    "missing_components": 3,
    "completeness_percentage": 73.33
  }
}
```

## Architecture

```
price_input_validator/
├── models.py              # Pydantic models for all data structures
├── screenshot_analyzer.py # GPT-4 Vision analysis
├── input_validator.py     # Playwright-based validation
├── gap_analyzer.py        # LLM-based gap detection
├── main.py               # Main orchestrator & CLI
└── __init__.py           # Package exports
```

## Models

### LabelsJSON
Input JSON structure with price element and list of inputs.

### LabelData
Validation result for a single input element with XPath, verification status, and reasoning.

### IdentifiedComponent
Component identified from screenshot analysis with label, type, and price relevance.

### MissingComponent
Component found on page but missing from JSON configuration.

### ValidationResult
Complete validation output with all components, validations, gaps, and summary.

## How It Works

1. **Screenshot Capture**: Uses Playwright to capture full-page screenshot
2. **Vision Analysis**: Sends screenshot to GPT-4 Vision to identify all price-relevant inputs
3. **XPath Generation**: Generates XPath selectors for each JSON input
4. **Live Validation**: Uses Playwright to verify each element exists on the actual page
5. **Gap Detection**: Uses LLM to fuzzy-match and identify missing components
6. **Report Generation**: Combines all findings into comprehensive results

## Error Handling

- Elements not found on page are marked as `verified: false` with explanatory reason
- Vision analysis errors fall back to returning empty component list
- Gap analysis errors fall back to simple label matching
- All errors are logged and don't crash the entire validation

## Tips

- Use specific selectors (ID, name) for better XPath matching
- Ensure page is fully loaded before validation (handled automatically)
- Review missing components - they may be legitimate gaps in your JSON
- Check failed validations - XPath may need refinement

## Troubleshooting

**Vision analysis fails:**
- Check Azure OpenAI credentials
- Verify model supports vision (gpt-4-vision-preview, gpt-4-turbo, etc.)
- Ensure image size is within limits

**Elements not found:**
- Check if page requires authentication
- Verify XPath selectors are correct
- Check if elements are in iframes
- Ensure page has finished loading

**Missing components reported incorrectly:**
- Review the fuzzy matching logic
- Check label differences between vision and JSON
- Consider semantic variations in naming

## License

MIT

## Contributing

Contributions welcome! Please ensure all Pydantic models are properly typed and include unit tests.

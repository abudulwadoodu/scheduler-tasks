# Quick Start Guide

## Installation

1. **Install dependencies:**
```bash
cd /Users/Mathew/Documents/Gordian/AutoScrape
pip install -r price_input_validator/requirements.txt
```

2. **Install Playwright browsers:**
```bash
playwright install chromium
```

3. **Set up environment variables:**

Create or update your `.env` file in the AutoScrape root directory:
```env
AZURE_API_KEY=your_azure_openai_key
AZURE_API_BASE=https://your-resource.openai.azure.com/
AZURE_API_VERSION=2024-02-15-preview
AZURE_API_MODEL=gpt-4
```

## Basic Usage

### Option 1: Command Line

```bash
# Run validation
python -m price_input_validator.main labels.json https://example.com/product

# With custom output file
python -m price_input_validator.main labels.json https://example.com/product --output my_results.json

# With UI flow hint (optional)
python -m price_input_validator.main labels.json https://example.com/product --output my_results.json --ui-flow-hint "Select Width dropdown before Height"
```

### Option 2: Python Script

```python
from price_input_validator import PriceInputValidator

# Initialize
validator = PriceInputValidator()

# Run validation (with optional UI flow hint)
result = validator.validate(
  labels_json_path="your_labels.json",
  web_url="https://your-site.com/product",
  output_path="results.json",
  ui_flow_hint="Select Width dropdown before Height"  # Optional
)

# Check results
print(f"Completeness: {result.summary['completeness_percentage']}%")
print(f"Missing components: {len(result.missing_components)}")
```

## What You'll Get

The validator will:

1. **📸 Capture** a screenshot of the webpage
2. **👁️ Analyze** it with GPT-4 Vision to identify ALL price-relevant inputs
3. **✅ Validate** each input in your JSON against the actual webpage
4. **📊 Report** gaps between what's on the page and what's in your JSON

## Output

You'll receive:

- **required_components**: All inputs identified by vision AI
- **validated_inputs**: Status of each JSON input (verified/failed)
- **missing_components**: Inputs on page but not in JSON
- **summary**: Statistics and completeness percentage

## Example Output

```
📊 VALIDATION SUMMARY
================================================================================
Vision Components Found: 15
JSON Inputs Provided: 12
Successfully Verified: 11
Failed Validations: 1
Missing from JSON: 3
Completeness: 73.33%

⚠️ WARNINGS:
  • 1 input(s) from JSON could not be verified on page
  • 3 component(s) found on page but missing from JSON

🔴 MISSING COMPONENTS (3):
  • Delivery Options (select)
    └─ Dropdown for selecting delivery method
    └─ Reason: Likely overlooked during initial form analysis
```

## Next Steps

1. Review the validation results
2. Update your JSON with missing components
3. Fix any failed validations (update XPath selectors)
4. Re-run validation until completeness is high (>90%)
5. Use the validated JSON for your scraping operations

## Troubleshooting

**ImportError: No module named 'price_input_validator'**
- Make sure you're in the AutoScrape directory when running commands
- Use `python -m price_input_validator.main` (not just `python main.py`)

**Azure OpenAI errors**
- Verify your `.env` file has correct credentials
- Check that your model name is correct
- Ensure your Azure OpenAI resource has the model deployed

**Playwright errors**
- Run `playwright install chromium` to install browser
- Check internet connectivity for page loading

**Elements not found**
- Page may require authentication (not currently supported)
- XPath selectors may need refinement
- Page may be heavily JavaScript-dependent (wait times may need adjustment)

## Advanced Usage

See [example.py](example.py) for more advanced usage patterns including:
- Accessing individual validation results
- Filtering and exporting specific findings
- Integration with scraping pipelines
- Conditional logic based on completeness scores

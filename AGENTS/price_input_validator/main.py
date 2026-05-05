"""
Main orchestrator for price input validation system.
"""
import os
import sys
import json
from pathlib import Path
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

from .models import LabelsJSON, ValidationResult
from .screenshot_analyzer import ScreenshotAnalyzer
from .input_validator import InputValidator
from .gap_analyzer import GapAnalyzer
from .price_extractor_agent import PriceExtractorAgent


class PriceInputValidator:
    """Main orchestrator for validating price-relevant inputs."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_version: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        Initialize the validator with Azure OpenAI credentials.
        
        Args:
            api_key: Azure OpenAI API key (or use env AZURE_API_KEY)
            api_base: Azure OpenAI endpoint (or use env AZURE_API_BASE)
            api_version: Azure OpenAI API version (or use env AZURE_API_VERSION)
            model: Model name (or use env AZURE_API_MODEL)
        """
        # Load environment variables
        load_dotenv()
        
        self.api_key = api_key or os.getenv("AZURE_API_KEY")
        self.api_base = api_base or os.getenv("AZURE_API_BASE")
        self.api_version = api_version or os.getenv("AZURE_API_VERSION")
        self.model = model or os.getenv("AZURE_API_MODEL", "gpt-4")
        
        if not all([self.api_key, self.api_base, self.api_version]):
            raise ValueError(
                "Azure OpenAI credentials required. Set AZURE_API_KEY, AZURE_API_BASE, "
                "and AZURE_API_VERSION environment variables or pass as arguments."
            )
        
        # Initialize components
        self.screenshot_analyzer = ScreenshotAnalyzer(
            api_key=self.api_key,
            api_base=self.api_base,
            api_version=self.api_version,
            model=self.model
        )
        
        self.input_validator = InputValidator(
            api_key=self.api_key,
            api_base=self.api_base,
            api_version=self.api_version,
            model=self.model
        )
        
        self.gap_analyzer = GapAnalyzer(
            api_key=self.api_key,
            api_base=self.api_base,
            api_version=self.api_version,
            model=self.model
        )

        self.price_extractor_agent = PriceExtractorAgent(
            api_key=self.api_key,
            api_base=self.api_base,
            api_version=self.api_version,
            model=self.model,
        )
    
    def validate(
        self,
        labels_json_path: str,
        web_url: str,
        output_path: Optional[str] = None
    ) -> ValidationResult:
        """
        Complete validation workflow.

        Args:
            labels_json_path: Path to JSON file with price and inputs
            web_url: URL of the webpage to analyze
            output_path: Optional path to save results JSON

        Returns:
            ValidationResult with all findings
        """
        print("=" * 80)
        print("🚀 PRICE INPUT VALIDATION SYSTEM")
        print("=" * 80)
        print(f"📄 JSON File: {labels_json_path}")
        print(f"🌐 Web URL: {web_url}")
        print("=" * 80)

        # Step 1: Load JSON
        print("\n[1/6] 📥 Loading JSON configuration...")
        with open(labels_json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        labels_json = LabelsJSON(**json_data)
        print(f"✅ Loaded {len(labels_json.inputs)} input definitions, "
              f"{len(labels_json.all_prices)} price candidates")

        # Step 2: Capture screenshot + analyse input components
        print("\n[2/6] 👁️ Capturing screenshot and analysing input components...")
        screenshot_bytes = self.screenshot_analyzer.capture_screenshot(web_url)
        vision_result = self.screenshot_analyzer.analyze_screenshot(screenshot_bytes)
        vision_components = vision_result.components
        vision_prices = vision_result.prices
        print(f"✅ Identified {len(vision_components)} price-relevant components")

        # Step 3: Price pipeline (3 sub-steps)
        price_analysis = None
        price_xpaths = None

        if labels_json.all_prices:
            # Step 3a: Vision-only — identify price clues from screenshot
            print("\n[3a/6] 🔍 Identifying prices from screenshot (vision)...")
            price_analysis = self.screenshot_analyzer.analyze_prices_from_screenshot(
                screenshot_bytes
            )
            _pwt = price_analysis.price_with_tax
            _pot = price_analysis.price_without_tax
            _bp  = price_analysis.base_price
            print(f"  price_with_tax   : {_pwt.value if _pwt else 'not found'}")
            print(f"  price_without_tax: {_pot.value if _pot else 'not found'}")
            print(f"  base_price       : {_bp.value  if _bp  else 'not found'}")

            # Step 3b: DOM validation — check all candidates against live page
            print("\n[3b/6] 🌐 Validating price candidates against live DOM...")
            validated_candidates = self.screenshot_analyzer.validate_all_price_candidates(
                web_url, labels_json.all_prices
            )
            verified_count = sum(1 for c in validated_candidates if c.verified)
            print(f"  {verified_count}/{len(validated_candidates)} candidates verified in DOM")
            for c in validated_candidates:
                status = "✓" if c.verified else "✗"
                preview = (c.text_content or "").strip()[:60]
                print(f"  {status} [{c.index}] {c.label!r}  xpath={c.xpath!r}  → {preview!r}")

            # Step 3c: Text-only LLM matching
            print("\n[3c/6] 🤝 Matching visual clues to DOM candidates (text LLM)...")
            price_xpaths = self.screenshot_analyzer.match_prices_to_xpaths(
                price_analysis, validated_candidates
            )
            for key in ("price_with_tax", "price_without_tax", "base_price"):
                entry = getattr(price_xpaths, key)
                if entry:
                    status = "✓" if entry.verified else "✗"
                    content = (entry.text_content or "").strip()[:60]
                    print(f"  {status} {key}: {entry.xpath!r} → {content!r}")
                else:
                    print(f"  — {key}: not matched")
        else:
            print("\n[3/6] ⚠️  No all_prices candidates — skipping price pipeline")

        # Step 4: Validate JSON inputs against live page
        print("\n[4/6] ✔️ Validating JSON inputs against webpage...")
        validated_inputs = self.input_validator.validate_inputs(web_url, labels_json)

        # Step 5: Gap analysis
        print("\n[5/6] 🔍 Analysing gaps...")
        missing_components = self.gap_analyzer.find_missing_components(
            vision_components, validated_inputs
        )
        summary = self.gap_analyzer.generate_summary(
            vision_components, validated_inputs, missing_components
        )

        # Step 6: Generate price extractor Python module
        price_extractor_output = None
        if price_analysis is not None and price_xpaths is not None:
            print("\n[6/6] 🛠️ Generating price extractor Python module...")
            extractor_path = self._extractor_path_from_output(output_path)
            price_extractor_output = self.price_extractor_agent.generate(
                price_analysis=price_analysis,
                price_xpaths=price_xpaths,
                output_path=extractor_path,
            )
        else:
            print("\n[6/6] ⏭️  Skipping price extractor (no price analysis available)")

        result = ValidationResult(
            required_components=vision_components,
            validated_inputs=validated_inputs,
            missing_components=missing_components,
            prices=vision_prices,
            price_xpaths=price_xpaths,
            price_analysis=price_analysis,
            price_extractor=price_extractor_output,
            summary=summary,
        )

        self._print_summary(result)

        if output_path:
            self._save_results(result, output_path)

        return result

    @staticmethod
    def _extractor_path_from_output(output_path: Optional[str]) -> str:
        """Derive a price-extractor .py path from the output JSON path (or use cwd)."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"price_extractor_{timestamp}.py"
        if output_path:
            return str(Path(output_path).parent / filename)
        return filename
    
    def _print_summary(self, result: ValidationResult):
        """Print a formatted summary of results."""
        print("\n" + "=" * 80)
        print("📊 VALIDATION SUMMARY")
        print("=" * 80)
        
        summary = result.summary
        print(f"Vision Components Found: {summary['total_vision_components']}")
        print(f"JSON Inputs Provided: {summary['total_json_inputs']}")
        print(f"Successfully Verified: {summary['verified_inputs']}")
        print(f"Failed Validations: {summary['failed_validations']}")
        print(f"Missing from JSON: {summary['missing_components']}")
        print(f"Completeness: {summary['completeness_percentage']}%")
        
        if summary.get('warnings'):
            print("\n⚠️ WARNINGS:")
            for warning in summary['warnings']:
                print(f"  • {warning}")
        
        # Print missing components details
        if result.missing_components:
            print(f"\n🔴 MISSING COMPONENTS ({len(result.missing_components)}):")
            for comp in result.missing_components:
                print(f"  • {comp.label} ({comp.type})")
                print(f"    └─ {comp.description}")
                print(f"    └─ Reason: {comp.reason_missing}")
        
        # Print failed validations
        failed = [inp for inp in result.validated_inputs if not inp.verified]
        if failed:
            print(f"\n❌ FAILED VALIDATIONS ({len(failed)}):")
            for inp in failed:
                print(f"  • {inp.label}")
                print(f"    └─ XPath: {inp.xpath}")
                print(f"    └─ Reason: {inp.reason}")
        
        print("\n" + "=" * 80)
    
    def _save_results(self, result: ValidationResult, output_path: str):
        """Save results to JSON file."""
        output_data = result.model_dump(exclude_none=True)
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved to: {output_path}")


def main():
    """CLI entry point."""
    if len(sys.argv) < 3:
        print("Usage: python -m price_input_validator.main <labels_json> <web_url> [output_json]")
        print("\nExample:")
        print("  python -m price_input_validator.main labels.json https://example.com/product")
        print("  python -m price_input_validator.main labels.json https://example.com/product results.json")
        sys.exit(1)
    
    labels_json_path = sys.argv[1]
    web_url = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else None
    
    # Auto-generate output path if not provided
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"validation_results_{timestamp}.json"
    
    try:
        validator = PriceInputValidator()
        validator.validate(labels_json_path, web_url, output_path)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

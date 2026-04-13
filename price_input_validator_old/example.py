"""
Example usage of the Price Input Validator.

This script demonstrates how to use the validator programmatically.
"""
import json
from pathlib import Path
from price_input_validator_old import PriceInputValidator, ValidationResult
INPUT_DIR = Path(__file__).resolve().parent / "input_jsons"

def main():
    """Example validation workflow."""
    
    # Example 1: Basic validation
    print("=" * 80)
    print("EXAMPLE 1: Basic Validation")
    print("=" * 80)
    
    validator = PriceInputValidator()
    labels_json_path = INPUT_DIR / "pipelaggingcom_armaflex-pipe-insulation-lagging-black-nitrile-foam-class-o-2m.json"
    print(f"Validating JSON: {labels_json_path}")
    # Run validation
    result = validator.validate(
        labels_json_path=labels_json_path,
        web_url="https://www.pipelagging.com/armaflex-pipe-insulation-lagging-black-nitrile-foam-class-o-2m",
        output_path="validation_results.json"
    )
    
    # Access results
    print(f"\n✅ Validation complete!")
    print(f"   - Vision identified: {len(result.required_components)} components")
    print(f"   - JSON provided: {len(result.validated_inputs)} inputs")
    print(f"   - Successfully verified: {sum(1 for v in result.validated_inputs if v.verified)}")
    print(f"   - Missing from JSON: {len(result.missing_components)}")
    
    # Example 2: Detailed analysis
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Detailed Analysis")
    print("=" * 80)
    
    # Show required components
    print("\n📋 Required Components (from vision analysis):")
    for i, comp in enumerate(result.required_components, 1):
        print(f"{i}. {comp.label} ({comp.type})")
        print(f"   └─ {comp.description}")
    
    # Show validation failures
    failed = [v for v in result.validated_inputs if not v.verified]
    if failed:
        print("\n❌ Failed Validations:")
        for v in failed:
            print(f"   • {v.label}")
            print(f"     XPath: {v.xpath}")
            print(f"     Reason: {v.reason}")
    
    # Show missing components
    if result.missing_components:
        print("\n🔴 Missing from JSON:")
        for comp in result.missing_components:
            print(f"   • {comp.label} ({comp.type})")
            print(f"     └─ {comp.description}")
            print(f"     └─ {comp.reason_missing}")
    
    # Example 3: Export specific findings
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Export Specific Findings")
    print("=" * 80)
    
    # Export only missing components
    missing_export = {
        "missing": [comp.model_dump() for comp in result.missing_components],
        "timestamp": result.summary.get("timestamp", "")
    }
    
    with open("missing_components.json", "w") as f:
        json.dump(missing_export, f, indent=2)
    print("💾 Missing components exported to: missing_components.json")
    
    # Export failed validations
    failed_export = {
        "failed": [v.model_dump() for v in failed],
        "count": len(failed)
    }
    
    with open("failed_validations.json", "w") as f:
        json.dump(failed_export, f, indent=2)
    print("💾 Failed validations exported to: failed_validations.json")
    
    # Example 4: Integration with scraping pipeline
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Integration Check")
    print("=" * 80)
    
    completeness = result.summary.get("completeness_percentage", 0)
    
    if completeness >= 90:
        print("✅ JSON configuration is highly complete (>= 90%)")
        print("   Safe to proceed with scraping.")
    elif completeness >= 70:
        print("⚠️ JSON configuration is moderately complete (70-89%)")
        print("   Review missing components before scraping.")
        print(f"   Missing: {', '.join(c.label for c in result.missing_components)}")
    else:
        print("❌ JSON configuration is incomplete (< 70%)")
        print("   Significant components missing. Update JSON before scraping.")
        print(f"   Missing: {', '.join(c.label for c in result.missing_components)}")
    
    return result


if __name__ == "__main__":
    # You'll need to update the paths and URL
    try:
        result = main()
    except FileNotFoundError:
        print("\n⚠️ Example files not found.")
        print("Update the paths in this script to point to your actual files.")
    except Exception as e:
        print(f"\n❌ Error: {e}")

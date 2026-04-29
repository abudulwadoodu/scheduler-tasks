"""
Gap analyzer to compare vision-identified components with JSON inputs.
"""
import json
from typing import List, Dict, Any
from openai import OpenAI
from .models import IdentifiedComponent, LabelData, MissingComponent


class GapAnalyzer:
    """Analyzes gaps between vision-identified components and JSON inputs."""
    
    def __init__(
        self,
        api_key: str,
        api_base: str,
        api_version: str,
        model: str = "gpt-4"
    ):
        """Initialize the gap analyzer with Azure OpenAI credentials."""
        self.client = OpenAI(
            api_key=api_key,
        )
        self.model = model
    
    def find_missing_components(
        self,
        vision_components: List[IdentifiedComponent],
        validated_inputs: List[LabelData]
    ) -> List[MissingComponent]:
        """
        Identify components from vision analysis that are missing in JSON.
        
        Args:
            vision_components: Components identified from screenshot
            validated_inputs: Validated components from JSON
            
        Returns:
            List of missing components
        """
        # Prepare data for LLM
        vision_data = [
            {
                "label": comp.label,
                "type": comp.type,
                "description": comp.description,
                "group": comp.group_context
            }
            for comp in vision_components
        ]
        
        json_data = [
            {
                "label": inp.label,
                "verified": inp.verified,
                "element": inp.identified_element,
                "input_type": inp.input_data.get("type", "") if inp.input_data else ""
            }
            for inp in validated_inputs
        ]
        
        system_prompt = """You are an expert at comparing UI components. Your task is to identify which components from a webpage screenshot are MISSING from a JSON configuration file.

Use fuzzy matching - labels may be slightly different (e.g., "Frame Width (mm)" vs "Frame Width"). Consider semantically similar labels as matches.

Return ONLY components that are clearly present in the vision analysis but NOT represented in the JSON inputs."""

        user_prompt = f"""Compare these two lists and identify components that are in the VISION list but missing from the JSON list.

VISION COMPONENTS (from screenshot):
{json.dumps(vision_data, indent=2)}

JSON INPUTS (from configuration):
{json.dumps(json_data, indent=2)}

For each missing component, provide:
1. label: The label from vision analysis
2. type: The input type
3. description: What this component does
4. reason_missing: Why you think it's missing from JSON (e.g., "oversight", "may not have been discovered during initial scraping")

Return your response as a JSON array of objects:
[
  {{
    "label": "Delivery Options",
    "type": "select",
    "description": "Dropdown for selecting delivery method",
    "reason_missing": "Likely overlooked during initial form analysis"
  }}
]

If all vision components are accounted for in the JSON, return an empty array: []"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"} if "1106" in self.model or "2024" in self.model else None
            )
            
            content = response.choices[0].message.content
            
            # Extract JSON
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()
            
            # Parse - handle both array and object with array
            parsed = json.loads(json_str)
            if isinstance(parsed, dict):
                # Check common keys
                missing_data = parsed.get("missing_components", parsed.get("missing", parsed.get("result", [])))
            else:
                missing_data = parsed
            
            # Convert to Pydantic models
            missing_components = [MissingComponent(**comp) for comp in missing_data]
            
            return missing_components
            
        except Exception as e:
            print(f"⚠️ Error analyzing gaps: {e}")
            # Fallback to simple label matching
            return self._simple_gap_analysis(vision_components, validated_inputs)
    
    def _simple_gap_analysis(
        self,
        vision_components: List[IdentifiedComponent],
        validated_inputs: List[LabelData]
    ) -> List[MissingComponent]:
        """
        Fallback simple gap analysis using label matching.
        
        Args:
            vision_components: Components identified from screenshot
            validated_inputs: Validated components from JSON
            
        Returns:
            List of missing components
        """
        json_labels = {inp.label.lower().strip() for inp in validated_inputs}
        missing = []
        
        for comp in vision_components:
            comp_label = comp.label.lower().strip()
            # Simple substring matching
            found = any(
                comp_label in json_label or json_label in comp_label
                for json_label in json_labels
            )
            
            if not found:
                missing.append(MissingComponent(
                    label=comp.label,
                    type=comp.type,
                    description=comp.description,
                    reason_missing="Not found in JSON inputs (simple label matching)"
                ))
        
        return missing
    
    def generate_summary(
        self,
        vision_components: List[IdentifiedComponent],
        validated_inputs: List[LabelData],
        missing_components: List[MissingComponent]
    ) -> Dict[str, Any]:
        """
        Generate a summary of the validation results.
        
        Args:
            vision_components: Components identified from screenshot
            validated_inputs: Validated components from JSON
            missing_components: Missing components
            
        Returns:
            Summary dictionary
        """
        verified_count = sum(1 for inp in validated_inputs if inp.verified)
        failed_count = len(validated_inputs) - verified_count
        
        summary = {
            "total_vision_components": len(vision_components),
            "total_json_inputs": len(validated_inputs),
            "verified_inputs": verified_count,
            "failed_validations": failed_count,
            "missing_components": len(missing_components),
            "completeness_percentage": round(
                (verified_count / len(vision_components) * 100) if vision_components else 0,
                2
            )
        }
        
        # Add warnings
        warnings = []
        if failed_count > 0:
            warnings.append(f"{failed_count} input(s) from JSON could not be verified on page")
        if missing_components:
            warnings.append(f"{len(missing_components)} component(s) found on page but missing from JSON")
        
        summary["warnings"] = warnings
        
        return summary

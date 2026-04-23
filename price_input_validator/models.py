"""
Pydantic models for price input validation system.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, PrivateAttr


class BoundingBox(BaseModel):
    """Bounding box coordinates for UI elements."""
    left: float
    top: float
    right: float
    bottom: float


class InputElement(BaseModel):
    """Represents an input element from the JSON."""
    label: str
    group_label: Optional[str] = None
    tag: str
    type: str = ""
    name: str = ""
    id: str = ""
    class_name: str = ""
    bbox: Optional[BoundingBox] = None
    is_price_relevant: bool = False


class PriceElement(BaseModel):
    """Represents the price element from the JSON."""
    label: str
    tag: str
    type: str = ""
    name: str = ""
    id: str = ""
    class_name: str = ""
    bbox: Optional[BoundingBox] = None


class LabelsJSON(BaseModel):
    """Complete structure of the input JSON file."""
    price: Optional[PriceElement] = None
    inputs: List[InputElement] = Field(default_factory=list)


class LabelData(BaseModel):
    """Validation result for a single input element."""
    label: str = Field('', description="The label or description from the input JSON.")
    xpath: str = Field('', description="The xpath used to locate the element.")
    verified: bool = Field(False, description="Whether the element was found on the page.")
    identified_element: Optional[str] = Field(
        None, 
        description="LLM-generated description of what the element represents in the actual webpage UI."
    )
    reason: str = Field('', description="Explanation or notes about the validation result.")
    input_data: Optional[Dict[str, Any]] = Field(None, description="Original input element data")
    outer_html: Optional[str] = Field(None, description="The outer HTML of the located element")


class IdentifiedComponent(BaseModel):
    """Component identified from screenshot analysis."""
    label: str = Field(..., description="The label or text associated with the input")
    type: str = Field(..., description="Type of input (text, select, radio, checkbox, etc.)")
    description: str = Field(..., description="Human-readable description of the component")
    price_relevance_reason: str = Field(..., description="Why this component affects price")
    group_context: Optional[str] = Field(None, description="Section or group this belongs to")


class MissingComponent(BaseModel):
    """Component that's on the page but missing from JSON."""
    label: str
    type: str
    description: str
    reason_missing: str = Field(..., description="Why this is likely missing from JSON")


class ValidationResult(BaseModel):
    """Complete validation result output."""
    required_components: List[IdentifiedComponent] = Field(
        default_factory=list,
        description="All price-relevant components identified from screenshot"
    )
    validated_inputs: List[LabelData] = Field(
        default_factory=list,
        description="Validation results for each input in JSON"
    )
    missing_components: List[MissingComponent] = Field(
        default_factory=list,
        description="Components found in screenshot but not in JSON"
    )
    summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary statistics and findings"
    )

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
    all_prices: List[PriceElement] = Field(default_factory=list)
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
    execution_order: int = Field(
        ...,
        description=(
            "1-based position in the sequence that components should be interacted with. "
            "Lower numbers must be completed first because later components may depend on them "
            "(e.g. a product-type selector that reveals additional options should have order 1)."
        )
    )
    execution_order_reason: str = Field(
        ...,
        description=(
            "Explanation of why this component has its assigned execution_order — "
            "what it unlocks, what it depends on, or why it is independent."
        )
    )


class PriceInfo(BaseModel):
    """Extracted price values from the page."""
    price_without_tax: Optional[str] = Field(None, description="Price excluding tax, as displayed (e.g. '£12.99'), or null if not visible")
    price_with_tax: Optional[str] = Field(None, description="Price including tax, as displayed (e.g. '£15.59'), or null if not visible")



class PriceXPathEntry(BaseModel):
    """A validated price XPath together with content extracted from the live page."""
    xpath: str = Field(..., description="XPath selector targeting the price element")
    verified: bool = Field(False, description="Whether the XPath matched exactly one element on the live page")
    text_content: Optional[str] = Field(
        None,
        description="Visible text extracted from the matched element (should contain the price value)"
    )
    outer_html: Optional[str] = Field(
        None,
        description="Outer HTML of the matched element, for debugging and cross-checking"
    )


class PriceXPaths(BaseModel):
    """XPaths for the identified price elements, enriched with live-page content."""
    price_with_tax: Optional[PriceXPathEntry] = Field(
        None, description="Element displaying the price including tax"
    )
    price_without_tax: Optional[PriceXPathEntry] = Field(
        None, description="Element displaying the price excluding tax"
    )
    base_price: Optional[PriceXPathEntry] = Field(
        None,
        description="Element displaying the undiscounted/original price before any offers are applied, if present"
    )

class PriceSelection(BaseModel):
    """LLM's selection of a single price candidate."""
    index: Optional[int] = Field(
        None,
        description="0-based index into the candidates list, or null if this price type is not present on the page"
    )
    reasoning: str = Field(..., description="Why this candidate was selected, or why none was chosen")


class PriceIdentificationResponse(BaseModel):
    """Structured LLM response for identifying price components from a screenshot."""
    price_with_tax: PriceSelection = Field(
        ...,
        description="The candidate that shows the price including tax"
    )
    price_without_tax: PriceSelection = Field(
        ...,
        description="The candidate that shows the price excluding tax"
    )
    base_price: PriceSelection = Field(
        ...,
        description=(
            "The candidate showing the undiscounted/original price before any offers or promotions "
            "are applied. Set index to null when no such price is separately displayed."
        )
    )


class VisualPriceClue(BaseModel):
    """A price value identified visually from the screenshot — no XPath, no DOM."""
    value: str = Field(..., description="The price string as seen in the screenshot, e.g. '£15.59'")
    with_tax_indicator: Optional[str] = Field(
        None,
        description="Visible label near the price signaling tax status (e.g. 'inc. VAT', 'ex. VAT')"
    )
    surrounding_text: Optional[str] = Field(
        None, description="Text immediately surrounding the price (e.g. 'Total: £15.59')"
    )
    visual_description: Optional[str] = Field(
        None, description="Description of the visual element (e.g. 'large bold price at top of page')"
    )


class ScreenshotPriceAnalysis(BaseModel):
    """Visual identification of price types from a screenshot — no XPaths, no DOM."""
    price_with_tax: Optional[VisualPriceClue] = Field(
        None, description="The price including tax as seen in the screenshot, or null if not visible"
    )
    price_without_tax: Optional[VisualPriceClue] = Field(
        None, description="The price excluding tax as seen in the screenshot, or null if not visible"
    )
    base_price: Optional[VisualPriceClue] = Field(
        None,
        description="The undiscounted/original price (e.g. struck-through RRP) if separately displayed, or null"
    )


class ValidatedPriceCandidate(BaseModel):
    """A price candidate from all_prices, validated against the live DOM."""
    index: int = Field(..., description="0-based index in the original all_prices list")
    label: str = Field(..., description="Human-readable label from the PriceElement")
    xpath: str = Field(..., description="XPath built from the PriceElement attributes")
    verified: bool = Field(False, description="True if exactly one element was found on the live page")
    text_content: Optional[str] = Field(None, description="Visible text of the matched element")
    outer_html: Optional[str] = Field(None, description="Outer HTML of the matched element")


class PriceMatchResponse(BaseModel):
    """Structured LLM response for matching visual price clues to validated DOM candidates."""
    price_with_tax: PriceSelection = Field(
        ..., description="Which validated candidate corresponds to the price including tax"
    )
    price_without_tax: PriceSelection = Field(
        ..., description="Which validated candidate corresponds to the price excluding tax"
    )
    base_price: PriceSelection = Field(
        ...,
        description="Which validated candidate is the undiscounted/original price, or null if none"
    )


class ExtractedPrice(BaseModel):
    """A single extracted price value."""
    with_tax: bool = Field(..., description="True if this price includes tax")
    price: float = Field(..., description="The numeric price value")
    currency_symbol: str = Field(..., description="The currency symbol (e.g. '£', '$', '€')")


class PriceExtractorCodeResponse(BaseModel):
    """Structured LLM response from the price extractor code-gen agent."""
    with_tax_reasoning: str = Field(
        ..., description="Chain-of-thought reasoning for the extract_price_with_tax function"
    )
    without_tax_reasoning: str = Field(
        ..., description="Chain-of-thought reasoning for the extract_price_without_tax function"
    )
    python_code: str = Field(
        ..., description="Complete Python module source code — no markdown fences, no ellipsis"
    )


class PriceExtractorOutput(BaseModel):
    """Result from the PriceExtractorAgent, including the saved file path."""
    with_tax_reasoning: str
    without_tax_reasoning: str
    python_code: str
    output_file_path: str = Field(..., description="Absolute path to the saved .py file")


class ComponentsAnalysisResponse(BaseModel):
    """Response model for screenshot analysis."""
    components: List[IdentifiedComponent] = Field(
        ...,
        description="List of all price-relevant components identified in the screenshot"
    )
    prices: PriceInfo = Field(
        default_factory=PriceInfo,
        description="Extracted price values currently visible on the page"
    )


class ElementDescription(BaseModel):
    """LLM-generated description of a UI element."""
    description: str = Field(
        ...,
        description="A concise 1-2 sentence description of what the element represents in the UI"
    )


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
    prices: Optional[PriceInfo] = Field(
        None,
        description="Price values extracted from the screenshot"
    )
    price_xpaths: Optional[PriceXPaths] = Field(
        None,
        description="XPaths for the identified price-with-tax and price-without-tax elements"
    )
    price_analysis: Optional[ScreenshotPriceAnalysis] = Field(
        None,
        description="Visual price identification from the screenshot (step 3a)"
    )
    price_extractor: Optional[PriceExtractorOutput] = Field(
        None,
        description="Generated price-extractor Python module details"
    )
    summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary statistics and findings"
    )

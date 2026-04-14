"""
Price Input Validator - Validate web form inputs using vision AI and Playwright.

This package provides tools to:
1. Identify price-relevant inputs from webpage screenshots using GPT-4 Vision
2. Validate JSON input configurations against actual webpages using Playwright
3. Find gaps between what's on the page and what's in your JSON config
"""

from .models import (
    LabelsJSON,
    InputElement,
    PriceElement,
    LabelData,
    IdentifiedComponent,
    MissingComponent,
    ValidationResult,
    PriceXPathEntry,
    PriceXPaths,
    VisualPriceClue,
    ScreenshotPriceAnalysis,
    ValidatedPriceCandidate,
    ExtractedPrice,
    PriceExtractorOutput,
)
from .screenshot_analyzer import ScreenshotAnalyzer
from .input_validator import InputValidator
from .gap_analyzer import GapAnalyzer
from .price_extractor_agent import PriceExtractorAgent
from .main import PriceInputValidator

__version__ = "1.0.0"

__all__ = [
    "PriceInputValidator",
    "ScreenshotAnalyzer",
    "InputValidator",
    "GapAnalyzer",
    "PriceExtractorAgent",
    "LabelsJSON",
    "InputElement",
    "PriceElement",
    "LabelData",
    "IdentifiedComponent",
    "MissingComponent",
    "ValidationResult",
    "PriceXPathEntry",
    "PriceXPaths",
    "VisualPriceClue",
    "ScreenshotPriceAnalysis",
    "ValidatedPriceCandidate",
    "ExtractedPrice",
    "PriceExtractorOutput",
]

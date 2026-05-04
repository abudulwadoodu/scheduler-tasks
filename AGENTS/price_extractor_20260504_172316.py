"""
Module for extracting price information (with and without tax) from webpage text content.
Implements extraction functions that raise NotImplementedError when no verified DOM element is found.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

@dataclass
class ExtractedPrice:
    with_tax: bool
    price: float
    currency_symbol: str

def extract_price_with_tax(text_content: str) -> ExtractedPrice:
    """
    Extracts the price including tax from the given text_content.
    Not implemented for this page as no verified DOM element was found.
    """
    raise NotImplementedError('price_with_tax not identified for this page')

def extract_price_without_tax(text_content: str) -> ExtractedPrice:
    """
    Extracts the price excluding tax from the given text_content.
    Not implemented for this page as no verified DOM element was found.
    """
    raise NotImplementedError('price_without_tax not identified for this page')

if __name__ == '__main__':
    # Demo: Both functions will raise NotImplementedError
    sample_text = '£6.82 inc VAT £8.18'
    try:
        print('With tax:', extract_price_with_tax(sample_text))
    except NotImplementedError as e:
        print('extract_price_with_tax:', e)
    try:
        print('Without tax:', extract_price_without_tax(sample_text))
    except NotImplementedError as e:
        print('extract_price_without_tax:', e)

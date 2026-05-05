"""
Module for extracting price information (with and without tax) from webpage text content.
Implements extraction functions that raise NotImplementedError when no verified DOM element is available.
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
    Extracts the price including tax from the given text content.
    Not implemented for this page as no verified DOM element was found.
    """
    raise NotImplementedError('price_with_tax not identified for this page')

def extract_price_without_tax(text_content: str) -> ExtractedPrice:
    """
    Extracts the price excluding tax from the given text content.
    Not implemented for this page as no verified DOM element was found.
    """
    raise NotImplementedError('price_without_tax not identified for this page')

if __name__ == '__main__':
    # Demo: Both functions will raise NotImplementedError
    try:
        print(extract_price_with_tax('£5.82 inc VAT £6.98'))
    except NotImplementedError as e:
        print(f'With tax: {e}')
    try:
        print(extract_price_without_tax('£5.82 inc VAT £6.98'))
    except NotImplementedError as e:
        print(f'Without tax: {e}')

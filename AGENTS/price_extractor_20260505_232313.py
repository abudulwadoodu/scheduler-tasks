"""
Module for extracting price information (with or without tax) from webpage text content.
Implements extraction functions that raise NotImplementedError when the price type is not identified or no DOM element is found.
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
    Raises NotImplementedError if the price type is not identified for this page.
    """
    raise NotImplementedError('price with tax not identified for this page')

def extract_price_without_tax(text_content: str) -> ExtractedPrice:
    """
    Extracts the price excluding tax from the given text_content.
    Raises NotImplementedError if the price type is not identified for this page.
    """
    raise NotImplementedError('price without tax not identified for this page')

if __name__ == '__main__':
    # Demo: Both functions will raise NotImplementedError
    try:
        print(extract_price_with_tax('£6.82 inc VAT £8.18'))
    except NotImplementedError as e:
        print(f'With tax: {e}')
    try:
        print(extract_price_without_tax('£6.82 inc VAT £8.18'))
    except NotImplementedError as e:
        print(f'Without tax: {e}')

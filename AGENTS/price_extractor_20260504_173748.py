"""
Module for extracting price with and without tax from text content.
Implements NotImplementedError for pages where no verified DOM element is found.
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
    For this page, no verified DOM element is found, so NotImplementedError is raised.
    """
    raise NotImplementedError('Price with tax not identified for this page')

def extract_price_without_tax(text_content: str) -> ExtractedPrice:
    """
    Extracts the price excluding tax from the given text_content.
    For this page, no verified DOM element is found, so NotImplementedError is raised.
    """
    raise NotImplementedError('Price without tax not identified for this page')

if __name__ == '__main__':
    # Demo: Both functions will raise NotImplementedError
    try:
        print(extract_price_with_tax('inc VAT: £8.34'))
    except NotImplementedError as e:
        print(f'With tax: {e}')
    try:
        print(extract_price_without_tax('ex VAT: £6.95'))
    except NotImplementedError as e:
        print(f'Without tax: {e}')

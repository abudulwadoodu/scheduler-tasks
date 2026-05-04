"""
Module for extracting price with and without tax from text content.
Implements NotImplementedError for this page as no verified DOM element was found.
"""

from dataclasses import dataclass
from decimal import Decimal

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
    try:
        print(extract_price_with_tax('inc VAT: £8.85'))
    except NotImplementedError as e:
        print(f'With tax: {e}')
    try:
        print(extract_price_without_tax('ex VAT: £7.38'))
    except NotImplementedError as e:
        print(f'Without tax: {e}')

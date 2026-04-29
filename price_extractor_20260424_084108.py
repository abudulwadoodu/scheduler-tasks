"""
Module for extracting with-tax and without-tax prices from product page text content.
Implements extraction logic only when a verified DOM element and pattern are available.
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
    Raises NotImplementedError if no verified DOM element is available for extraction.
    """
    raise NotImplementedError('with_tax not identified for this page')

def extract_price_without_tax(text_content: str) -> ExtractedPrice:
    """
    Extracts the price excluding tax from the given text_content.
    Raises NotImplementedError if no verified DOM element is available for extraction.
    """
    raise NotImplementedError('without_tax not identified for this page')

if __name__ == '__main__':
    # Demo: Both functions will raise NotImplementedError
    try:
        print(extract_price_with_tax('£14.20 inc VAT'))
    except NotImplementedError as e:
        print(f'with_tax: {e}')
    try:
        print(extract_price_without_tax('£11.83 ex VAT'))
    except NotImplementedError as e:
        print(f'without_tax: {e}')

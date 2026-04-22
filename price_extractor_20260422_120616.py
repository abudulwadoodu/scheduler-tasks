"""
Module for extracting price information (with and without tax) from text content.
Implements NotImplementedError for pages where no verified DOM element is found.
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
    Raises NotImplementedError if the price type is not identified for this page.
    """
    raise NotImplementedError('with-tax price not identified for this page')

def extract_price_without_tax(text_content: str) -> ExtractedPrice:
    """
    Extracts the price excluding tax from the given text_content.
    Raises NotImplementedError if the price type is not identified for this page.
    """
    raise NotImplementedError('without-tax price not identified for this page')

if __name__ == '__main__':
    # Demo: Both functions will raise NotImplementedError
    try:
        print(extract_price_with_tax('Inc VAT: £14.20'))
    except NotImplementedError as e:
        print(f'With tax: {e}')
    try:
        print(extract_price_without_tax('Ex VAT: £11.84'))
    except NotImplementedError as e:
        print(f'Without tax: {e}')

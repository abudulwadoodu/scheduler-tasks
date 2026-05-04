"""
Price extraction module for a page where no verified DOM elements were found for either price with tax or price without tax.
All extraction functions raise NotImplementedError as required by the specification.
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
    raise NotImplementedError('with_tax not identified for this page')

def extract_price_without_tax(text_content: str) -> ExtractedPrice:
    """
    Extracts the price excluding tax from the given text_content.
    Not implemented for this page as no verified DOM element was found.
    """
    raise NotImplementedError('without_tax not identified for this page')

if __name__ == '__main__':
    # Demo: Both functions will raise NotImplementedError
    try:
        print(extract_price_with_tax('Inc. VAT: £14.29'))
    except NotImplementedError as e:
        print(f'with_tax: {e}')
    try:
        print(extract_price_without_tax('Ex. VAT: £11.91'))
    except NotImplementedError as e:
        print(f'without_tax: {e}')

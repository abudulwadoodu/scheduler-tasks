"""
Module for extracting price information (with and without tax) from product page text content.
Implements ExtractedPrice dataclass and extraction functions.
"""
from dataclasses import dataclass

@dataclass
class ExtractedPrice:
    with_tax: bool
    price: float
    currency_symbol: str

def extract_price_with_tax(text_content: str) -> ExtractedPrice:
    """
    Extracts the price including tax from the given text_content.
    Raises NotImplementedError if this price type is not identified for the page.
    """
    raise NotImplementedError('Price with tax not identified for this page')

def extract_price_without_tax(text_content: str) -> ExtractedPrice:
    """
    Extracts the price excluding tax from the given text_content.
    Raises NotImplementedError if this price type is not identified for the page.
    """
    raise NotImplementedError('Price without tax not identified for this page')

if __name__ == '__main__':
    # Demo: Both functions will raise NotImplementedError
    try:
        print(extract_price_with_tax('Inc. VAT: £13.09'))
    except NotImplementedError as e:
        print(f'With tax: {e}')
    try:
        print(extract_price_without_tax('Ex. VAT: £10.91'))
    except NotImplementedError as e:
        print(f'Without tax: {e}')

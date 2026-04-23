"""
Module for extracting price information (with or without tax) from text content.

Defines ExtractedPrice dataclass and extraction functions for a specific observed format.
"""

import re
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
    Not implemented for this page.
    """
    raise NotImplementedError('with_tax not identified for this page')

def extract_price_without_tax(text_content: str) -> ExtractedPrice:
    """
    Extracts the price excluding tax from the given text_content.
    Looks for a line like 'Now £65.00 ex VAT'.
    """
    # Pattern: Now <currency><amount> ex VAT
    pattern = re.compile(r'Now\s*(?P<currency>[£$€])\s*(?P<price>\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*ex VAT', re.IGNORECASE)
    match = pattern.search(text_content)
    if not match:
        raise ValueError(f"Could not parse without_tax from: {text_content!r}")
    currency_symbol = match.group('currency')
    price_str = match.group('price').replace(',', '')
    price = float(Decimal(price_str))
    return ExtractedPrice(with_tax=False, price=price, currency_symbol=currency_symbol)

if __name__ == '__main__':
    # Demo usage
    demo_text = 'Total Cost\nApril Offer Save £50 Was £115.00\nNow £65.00 ex VAT'
    try:
        price = extract_price_without_tax(demo_text)
        print(f"Extracted price (without tax): {price}")
    except Exception as e:
        print(f"Error extracting price without tax: {e}")

    try:
        price = extract_price_with_tax(demo_text)
        print(f"Extracted price (with tax): {price}")
    except NotImplementedError as nie:
        print(f"NotImplementedError: {nie}")
    except Exception as e:
        print(f"Error extracting price with tax: {e}")

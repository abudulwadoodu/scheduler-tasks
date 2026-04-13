"""
Module for extracting price information (with or without tax) from text content.
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
    Looks for the pattern: 'Now £<amount> inc. VAT' (case-insensitive).
    Raises ValueError if the pattern is not found.
    """
    # Regex: 'Now' (case-insensitive), optional whitespace, '£', price, optional whitespace, 'inc', optional '.', whitespace, 'VAT'
    pattern = re.compile(r"Now\s*£([0-9]+(?:\.[0-9]{2})?)\s*inc\.?\s*VAT", re.IGNORECASE)
    match = pattern.search(text_content)
    if not match:
        raise ValueError(f"Could not parse price with tax from: {text_content!r}")
    price_str = match.group(1)
    price = float(Decimal(price_str))
    return ExtractedPrice(with_tax=True, price=price, currency_symbol='£')

def extract_price_without_tax(text_content: str) -> ExtractedPrice:
    """
    No price without tax is identified for this page.
    """
    raise NotImplementedError('Price without tax not identified for this page')

if __name__ == '__main__':
    # Demo for extract_price_with_tax
    demo_text = 'Total Cost\nApril Offer Save £50 Was £115.00\nNow £65.00 inc. VAT'
    try:
        result = extract_price_with_tax(demo_text)
        print(f"Extracted (with tax): {result}")
    except Exception as e:
        print(f"Error extracting price with tax: {e}")

    # Demo for extract_price_without_tax
    try:
        result = extract_price_without_tax(demo_text)
        print(f"Extracted (without tax): {result}")
    except NotImplementedError as nie:
        print(f"NotImplementedError: {nie}")
    except Exception as e:
        print(f"Error extracting price without tax: {e}")

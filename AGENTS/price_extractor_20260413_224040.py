"""
Price extraction module for a specific observed pattern: 'Now £X inc. VAT' in a 'Total Cost' box.

Provides functions to extract with-tax and without-tax prices from text content.
"""
import re
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
    Looks for the pattern: 'Now £X inc. VAT' (case-insensitive, optional period in 'inc.').
    Raises ValueError if the pattern is not found.
    """
    # Regex: 'Now' (case-insensitive), optional whitespace, '£', price, optional whitespace, 'inc', optional '.', whitespace, 'VAT'
    pattern = re.compile(r"Now\s+£([0-9]+(?:\.[0-9]{2})?)\s+inc\.?\s+VAT", re.IGNORECASE)
    match = pattern.search(text_content)
    if not match:
        raise ValueError(f"Could not parse with-tax price from: {text_content!r}")
    price_str = match.group(1)
    price = float(Decimal(price_str))
    return ExtractedPrice(with_tax=True, price=price, currency_symbol='£')

def extract_price_without_tax(text_content: str) -> ExtractedPrice:
    """
    No price without tax is identified for this page.
    """
    raise NotImplementedError('without-tax price not identified for this page')

if __name__ == '__main__':
    # Demo with observed text_content
    demo_text = 'Total Cost\nApril Offer Save £50 Was £115.00\nNow £65.00 inc. VAT'
    try:
        price_with_tax = extract_price_with_tax(demo_text)
        print('With-tax price:', price_with_tax)
    except Exception as e:
        print('With-tax extraction error:', e)

    try:
        price_without_tax = extract_price_without_tax(demo_text)
        print('Without-tax price:', price_without_tax)
    except Exception as e:
        print('Without-tax extraction error:', e)

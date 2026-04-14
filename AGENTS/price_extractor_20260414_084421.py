"""
Module for extracting price information (with or without tax) from text content.
Only standard library is used. See demo at the bottom.
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
    Looks for a pattern like 'Now £65.00 inc. VAT'.
    Raises ValueError if not found.
    """
    # Regex: 'Now' (optional whitespace) '£' (amount) (optional whitespace) 'inc.' (optional whitespace) 'VAT'
    pattern = re.compile(r"Now\s*£([0-9]+(?:\.[0-9]{2})?)\s*inc\.?\s*VAT", re.IGNORECASE)
    match = pattern.search(text_content)
    if not match:
        raise ValueError(f"Could not parse price with tax from: {text_content!r}")
    amount_str = match.group(1)
    price = float(Decimal(amount_str))
    return ExtractedPrice(with_tax=True, price=price, currency_symbol='£')

def extract_price_without_tax(text_content: str) -> ExtractedPrice:
    """
    No price without tax identified for this page.
    """
    raise NotImplementedError('Price without tax not identified for this page')

if __name__ == '__main__':
    # Demo usage
    demo_text = 'Total Cost\nApril Offer Save £50 Was £115.00\nNow £65.00 inc. VAT'
    try:
        price = extract_price_with_tax(demo_text)
        print(f"With tax: {price}")
    except Exception as e:
        print(f"With tax extraction failed: {e}")

    try:
        price = extract_price_without_tax(demo_text)
        print(f"Without tax: {price}")
    except NotImplementedError as e:
        print(f"Without tax extraction: {e}")

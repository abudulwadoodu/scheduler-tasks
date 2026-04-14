"""
Module for extracting price information (with or without tax) from text content.
Only standard library is used. See demo at bottom.
"""
import re
from decimal import Decimal
from dataclasses import dataclass

@dataclass
class ExtractedPrice:
    with_tax: bool
    price: float
    currency_symbol: str

def extract_price_with_tax(text_content: str) -> ExtractedPrice:
    """
    Extracts the price including tax from the given text_content.
    Looks for the pattern: 'Now £<amount> inc. VAT' (case-insensitive).
    Raises ValueError if not found.
    """
    # Regex: 'Now £65.00 inc. VAT' (allow optional period, case-insensitive, flexible whitespace)
    pattern = re.compile(
        r'Now\s*([£$€])\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*inc\.?\s*VAT',
        re.IGNORECASE
    )
    match = pattern.search(text_content)
    if not match:
        raise ValueError(f"Could not parse price with tax from: {text_content!r}")
    currency_symbol = match.group(1)
    price_str = match.group(2).replace(',', '')
    price = float(Decimal(price_str))
    return ExtractedPrice(with_tax=True, price=price, currency_symbol=currency_symbol)

def extract_price_without_tax(text_content: str) -> ExtractedPrice:
    """
    No price without tax identified for this page.
    """
    raise NotImplementedError('Price without tax not identified for this page')

if __name__ == '__main__':
    # Demo with observed text_content
    demo_text = 'Total Cost\nApril Offer Save £50 Was £115.00\nNow £65.00 inc. VAT'
    try:
        result = extract_price_with_tax(demo_text)
        print('With tax:', result)
    except Exception as e:
        print('With tax extraction failed:', e)
    try:
        result = extract_price_without_tax(demo_text)
        print('Without tax:', result)
    except NotImplementedError as nie:
        print('Without tax extraction:', nie)

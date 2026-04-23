"""
scraper_agent/validator.py
==========================
Validates the stdout of an executed scraper script and extracts the price.

A valid result must:
  - Contain a line matching "Extracted price: <value>"
  - Have a value that parses as a float after stripping currency symbols
"""

import re


def validate_result(stdout: str) -> str | None:
    """
    Parse *stdout* for a valid price.

    Returns:
        The price string (e.g. "24.99") on success.
        None if no valid price is found.
    """
    match = re.search(r"Extracted price:\s*([^\n]+)", stdout)
    if not match:
        return None

    price_str = match.group(1).strip()

    # Must contain at least one digit
    if not re.search(r"\d", price_str):
        return None

    # Must parse as a float after stripping known non-numeric characters
    cleaned = re.sub(r"[$€£¥₹,\s]", "", price_str)
    try:
        float(cleaned)
        return price_str
    except ValueError:
        return None


def build_error_context(stdout: str, stderr: str, returncode: int) -> str:
    """
    Construct a human-readable error string from a failed execution,
    suitable for passing back to the generator as fix context.
    """
    if returncode != 0 and stderr.strip():
        return stderr.strip()

    if returncode != 0:
        return (
            f"Script exited with code {returncode}.\n"
            f"stdout: {stdout.strip()}"
        )

    return (
        f"Script exited cleanly (code 0) but no valid price was found in output.\n"
        f"stdout: {stdout.strip()}"
    )

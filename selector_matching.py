import re
from lxml import etree


def extract_mm_candidates(comment: str) -> list:
    """
    Extract all mm values from comment string as integers.
    e.g. "Armaflex 32mm Class O 21.3/22mm Dia" → [32, 21, 22]
    """
    matches = re.findall(r"(\d+\.?\d*)\s*mm", comment, re.IGNORECASE)
    return [round(float(m)) for m in matches]  # round to int e.g. 21.3 → 21


def extract_options_from_xpath(html_source: str, xpaths: dict) -> dict:
    """
    Parse HTML and extract <option> values for each dropdown xpath.
    Returns: { name: [(option_text, numeric_value), ...] }
    """
    parser = etree.HTMLParser()
    tree = etree.fromstring(html_source.encode("utf-8", errors="replace"), parser)

    dropdown_options = {}
    for name, xpath in xpaths.items():
        elements = tree.xpath(xpath)
        if not elements:
            raise ValueError(f"XPath not found: {xpath}")
        select_el = elements[0]
        options = []
        for opt in select_el.xpath(".//option"):
            text = (opt.text or "").strip()
            if not text or re.match(r"(?i)^(choose|select|--)", text):
                continue
            # Extract leading number only — handles "32 + £0.23", "6", "22mm", "13 - £0.64"
            match = re.match(r"^(\d+\.?\d*)", text)
            numeric = round(float(match.group(1))) if match else None
            options.append((text, numeric))
        dropdown_options[name] = options

    return dropdown_options


def match_candidates_to_dropdowns(
    comment: str,
    xpaths: dict,
    html_source: str,
    fuzzy_tolerance: int = 1  # ±1 integer unit
) -> dict:
    """
    Main preprocessing function.
    Returns: { xpath_string → option_text_to_select }
    Raises ValueError if a candidate cannot be matched to any dropdown.
    """
    dropdown_options = extract_options_from_xpath(html_source, xpaths)
    candidates = extract_mm_candidates(comment)

    if not candidates:
        raise ValueError(f"No mm values found in comment: '{comment}'")

    print(f"Candidates from comment: {candidates}")
    print(f"Dropdown options discovered:")
    for name, opts in dropdown_options.items():
        print(f"  {name}: {[(t, n) for t, n in opts]}")

    result = {}
    used_dropdowns = set()

    for candidate in candidates:
        best_match_text = None
        best_diff = float("inf")
        best_dropdown_name = None

        for name, options in dropdown_options.items():
            if name in used_dropdowns:
                continue
            for option_text, numeric in options:
                if numeric is None:
                    continue
                diff = abs(numeric - candidate)
                if diff <= fuzzy_tolerance and diff < best_diff:
                    best_diff = diff
                    best_match_text = option_text
                    best_dropdown_name = name

        if best_match_text is None:
            available = "\n".join(
                f"  - {name}: {[o[0] for o in opts]}"
                for name, opts in dropdown_options.items()
                if name not in used_dropdowns
            )
            raise ValueError(
                f"Could not match '{candidate}mm' to any remaining dropdown.\n"
                f"Available options:\n{available}"
            )

        if best_diff > 0:
            print(f"# Fuzzy matched {candidate}mm → '{best_match_text}' ({best_dropdown_name})")
        else:
            print(f"# Exact matched {candidate}mm → '{best_match_text}' ({best_dropdown_name})")

        result[xpaths[best_dropdown_name]] = best_match_text
        used_dropdowns.add(best_dropdown_name)

    return result


# --- USAGE EXAMPLE ---
if __name__ == "__main__":
    xpaths = {
        "pipe_size": '//*[@id="attribute186"]',
        "thickness": '//*[@id="attribute185"]',
    }
    comment = "Armaflex 9mm Class O Insulation Tube 15mm Dia"
    html_source = open("page1.html", encoding="utf-8").read()

    selections = match_candidates_to_dropdowns(comment, xpaths, html_source)

    print("\nDropdown selections to pass to scraping script:")
    for xpath, value in selections.items():
        print(f"  xpath: {xpath!r}  →  select: {value!r}")

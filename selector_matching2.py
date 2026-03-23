import re
import json
from lxml import etree


def extract_mm_candidates(comment: str) -> list:
    """Extract mm values as rounded ints, preserving order of appearance."""
    matches = re.findall(r"(\d+\.?\d*)\s*mm", comment, re.IGNORECASE)
    return [round(float(m)) for m in matches]


def extract_options_from_xpath(html_source: str, xpaths: dict) -> dict:
    """Parse HTML and return {action_name: [(option_text, numeric), ...]}"""
    parser = etree.HTMLParser()
    tree = etree.fromstring(html_source.encode("utf-8", errors="replace"), parser)

    dropdown_options = {}
    for name, xpath in xpaths.items():
        elements = tree.xpath(xpath)
        if not elements:
            raise ValueError(f"XPath not found: {xpath}")
        options = []
        for opt in elements[0].xpath(".//option"):
            text = (opt.text or "").strip()
            if not text or re.match(r"(?i)^(choose|select|--)", text):
                continue
            match = re.match(r"^(\d+\.?\d*)", text)
            numeric = round(float(match.group(1))) if match else None
            options.append((text, numeric))
        dropdown_options[name] = options
    return dropdown_options


def learn_rule(comment: str, xpaths: dict, html_source: str, fuzzy_tolerance: int = 1) -> dict:
    """
    One-time learning phase.
    Matches mm values from comment to dropdowns via HTML option lookup.
    Returns a reusable rule: { action_name: positional_index_in_extracted_list }

    Example output:
      { "action1": 1, "action2": 0 }
    Meaning: action1 gets numerical_values[1], action2 gets numerical_values[0]
    """
    dropdown_options = extract_options_from_xpath(html_source, xpaths)
    candidates = extract_mm_candidates(comment)

    if not candidates:
        raise ValueError(f"No mm values found in comment: '{comment}'")

    print(f"Extracted candidates (with positions): {list(enumerate(candidates))}")

    rule = {}          # action_name → index in candidates list
    used_actions = set()

    for idx, candidate in enumerate(candidates):
        best_action = None
        best_diff = float("inf")

        for action_name, options in dropdown_options.items():
            if action_name in used_actions:
                continue
            for _, numeric in options:
                if numeric is None:
                    continue
                diff = abs(numeric - candidate)
                if diff <= fuzzy_tolerance and diff < best_diff:
                    best_diff = diff
                    best_action = action_name

        if best_action is None:
            available = "\n".join(
                f"  {name}: {[o[1] for o in opts if o[1]]}"
                for name, opts in dropdown_options.items()
                if name not in used_actions
            )
            raise ValueError(
                f"Could not match '{candidate}mm' (index {idx}) to any dropdown.\n"
                f"Remaining options:\n{available}"
            )

        rule[best_action] = idx
        used_actions.add(best_action)
        label = "exact" if best_diff == 0 else f"fuzzy ±{best_diff}"
        print(f"  {candidate}mm (index {idx}) → {best_action} [{label}]")

    print(f"\nRule learned: {rule}")
    return rule


def apply_rule(comment: str, rule: dict) -> dict:
    """
    Reuse phase — no HTML needed.
    Applies learned positional rule to any new comment.
    Returns: { action_name: mm_value_string }
    """
    candidates = extract_mm_candidates(comment)

    if not candidates:
        raise ValueError(f"No mm values found in comment: '{comment}'")

    result = {}
    for action_name, idx in rule.items():
        if idx >= len(candidates):
            raise ValueError(
                f"Rule expects index {idx} for '{action_name}' "
                f"but comment only has {len(candidates)} value(s): {candidates}"
            )
        result[action_name] = f"{candidates[idx]}mm"

    return result


def save_rule(rule: dict, filepath: str):
    """Persist rule to JSON for reuse across sessions."""
    with open(filepath, "w") as f:
        json.dump(rule, f, indent=2)
    print(f"Rule saved to {filepath}")


def load_rule(filepath: str) -> dict:
    """Load a previously saved rule."""
    with open(filepath) as f:
        return json.load(f)


# ── USAGE ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    xpaths = {
        "action1": "//*[@id='attribute186']",
        "action2": "//*[@id='attribute185']",
    }

    # ── PHASE 1: Learn rule once using HTML source ──
    print("=== LEARNING PHASE ===")
    training_comment = "Armaflex 9mm Class O Insulation Tube 15mm Dia"
    html_source = open("page1.html", encoding="utf-8").read()

    rule = learn_rule(training_comment, xpaths, html_source)
    # rule → { "action1": 1, "action2": 0 }

    save_rule(rule, "dropdown_rule.json")

    # ── PHASE 2: Reuse rule on new comments (no HTML needed) ──
    print("\n=== APPLY PHASE ===")
    rule = load_rule("dropdown_rule.json")

    test_comments = [
        "Armaflex 32mm Class O Insulation Tube 22mm Dia",
        "Armaflex 13mm Class O Insulation Tube 28mm Dia",
        "Armaflex 6mm Class O Insulation Tube 15mm Dia",
    ]

    for c in test_comments:
        result = apply_rule(c, rule)
        print(f"  {c}")
        print(f"    → {result}\n")

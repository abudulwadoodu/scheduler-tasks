"""
html_trimmer.py
───────────────
Trims a product page HTML down to only the fragments Claude needs
to identify the price XPath and variant selector XPaths.

Strategy
────────
1. Strip all noise tags (script, style, svg, head, meta …)
2. Restrict search scope to <main> / <article> only — everything outside
   (header, footer, nav, sidebars) is ignored entirely
3. Within scope, find two kinds of anchor elements:
     a) Price anchors  — elements whose text/class/id contain price keywords
     b) Control anchors — <select>, <input> (non-hidden), <button type=submit>
4. For each anchor walk UP at most _PARENT_LEVELS, stopping at ceiling tags
5. Deduplicate containers
6. Serialise keeping only XPath-useful attributes; strip everything else
7. Collapse whitespace, apply hard char cap

Result: 7000+ line page → ~200-600 lines
"""

from __future__ import annotations

import re
from typing import Optional
from bs4 import BeautifulSoup, Tag


# ── Strip entirely ───────────────────────────────────────────────────────── #
_STRIP_TAGS = {
    "script", "style", "svg", "noscript", "head",
    "meta", "link", "iframe", "canvas", "video", "audio",
    "template", "picture",
}

# ── Attributes to KEEP (everything else stripped) ────────────────────────── #
_KEEP_ATTRS = {
    "id", "class", "name", "type", "value", "for",
    "action", "method", "placeholder", "aria-label",
    "itemprop", "itemtype", "selected", "disabled",
    "data-price-amount", "data-price-type", "data-product-id",
}

# ── Price signal patterns ─────────────────────────────────────────────────── #
_PRICE_KEYWORDS = re.compile(
    r"\b(price|cost|amount|total|excl|incl|tax|vat|subtotal|"
    r"unit.?price|net|gross|£|\$|€|¥|₹)\b",
    re.IGNORECASE,
)
_PRICE_CLASS_RE = re.compile(
    r"price|cost|amount|total|excl|incl|tax|vat|pricing",
    re.IGNORECASE,
)

# ── Scope: only search inside these tags ─────────────────────────────────── #
_SCOPE_TAGS = {"main", "article"}

# ── IDs/classes of known noise sections to skip even inside <main> ────────── #
_NOISE_IDS = re.compile(
    r"related|upsell|cross.?sell|recently.?viewed|newsletter|"
    r"review|social|share|breadcrumb|widget|slider|carousel",
    re.IGNORECASE,
)

# ── Parent walk ceiling — never walk past these ───────────────────────────── #
_CEILING_TAGS = {"main", "article", "section", "form", "body", "html"}

# ── Control tags (variant selectors) ─────────────────────────────────────── #
_CONTROL_TAGS = {"select", "textarea"}  # inputs handled separately below

# ── Max parent levels to walk up ─────────────────────────────────────────── #
_PARENT_LEVELS = 2


# ── Helpers ──────────────────────────────────────────────────────────────── #

def _in_noise_section(el: Tag) -> bool:
    """Return True if el lives inside a known noise container."""
    for parent in el.parents:
        if not isinstance(parent, Tag):
            continue
        pid   = parent.get("id") or ""
        pcls  = " ".join(parent.get("class") or [])
        if _NOISE_IDS.search(pid) or _NOISE_IDS.search(pcls):
            return True
    return False


def _in_scope(el: Tag) -> bool:
    """Return True if el is a descendant of a _SCOPE_TAGS element."""
    return any(p.name in _SCOPE_TAGS for p in el.parents if isinstance(p, Tag))


def _is_ancestor(candidate: Tag, node: Tag) -> bool:
    current = node.parent
    while current is not None:
        if current is candidate:
            return True
        current = current.parent
    return False


def _walk_up(anchor: Tag) -> Tag:
    """Walk up _PARENT_LEVELS from anchor, stopping at ceiling tags."""
    node = anchor
    for _ in range(_PARENT_LEVELS):
        parent = node.parent
        if parent is None or not isinstance(parent, Tag):
            break
        if parent.name in _CEILING_TAGS:
            break
        node = parent
    return node


def _prune_attrs(tag: Tag) -> None:
    """Recursively keep only _KEEP_ATTRS on every element."""
    if not isinstance(tag, Tag):
        return
    tag.attrs = {k: v for k, v in (tag.attrs or {}).items() if k in _KEEP_ATTRS}
    for child in tag.children:
        if isinstance(child, Tag):
            _prune_attrs(child)


def _serialise(tag: Tag) -> str:
    import copy
    clone = copy.copy(tag)
    _prune_attrs(clone)
    out = str(clone)
    out = re.sub(r' [\w-]+=""', "", out)
    return out


# ── Main public function ──────────────────────────────────────────────────── #

def trim_html(
    html: str,
    extra_keywords: Optional[list[str]] = None,
    max_chars: int = 400000,
    debug: bool = False,
) -> str:
    """
    Return trimmed HTML containing only price elements and variant selectors.

    Args:
        html:             Raw HTML from page.content().
        extra_keywords:   Additional price-hint keywords for this specific site.
        max_chars:        Hard output cap (default 40 000 chars ≈ 10k tokens).
        debug:            Print reduction stats when True.

    Returns:
        Trimmed HTML string ready to send to Claude.
    """
    kw_pattern = _PRICE_KEYWORDS
    if extra_keywords:
        combined = (
            _PRICE_KEYWORDS.pattern.rstrip(r"\b)")
            + "|" + "|".join(re.escape(k) for k in extra_keywords)
            + r")\b"
        )
        kw_pattern = re.compile(combined, re.IGNORECASE)

    soup = BeautifulSoup(html, "html.parser")

    # ── 1. Strip noise tags ───────────────────────────────────────────────── #
    for tag in soup.find_all(_STRIP_TAGS):
        tag.decompose()

    # ── 2. Collect anchors (inside <main>/<article> only, skip noise sections) #
    anchors: list[Tag] = []

    # a) Price anchors
    for el in soup.find_all(True):
        if not isinstance(el, Tag):
            continue
        if not _in_scope(el):
            continue
        if _in_noise_section(el):
            continue
        text    = el.get_text(" ", strip=True)
        classes = " ".join(el.get("class") or [])
        el_id   = el.get("id", "")
        if (kw_pattern.search(text)
                or _PRICE_CLASS_RE.search(classes)
                or _PRICE_CLASS_RE.search(el_id)):
            anchors.append(el)

    # b) Control anchors: <select> and <button type="submit"> inside scope
    for el in soup.find_all(list(_CONTROL_TAGS) + ["button", "input"]):
        if not isinstance(el, Tag):
            continue
        if not _in_scope(el):
            continue
        if _in_noise_section(el):
            continue
        # input: keep only non-hidden, non-form_key ones that look like qty/options
        if el.name == "input":
            itype = el.get("type", "text").lower()
            iname = el.get("name", "")
            if itype == "hidden":
                continue
            if iname in {"form_key", "uenc", "related_product"}:
                continue
        # button: keep only submit buttons (Add to Cart) inside product forms
        if el.name == "button":
            if el.get("type", "").lower() not in {"submit", ""}:
                continue
            # skip tiny nav/wishlist/close buttons
            aria = el.get("aria-label", "")
            if re.search(r"close|wish|nav|toggle|prev|next|fullscreen|play", aria, re.I):
                continue
        anchors.append(el)

    if debug:
        print(f"[TRIM] Anchors: {len(anchors)}")

    # ── 3. Walk up to context containers ─────────────────────────────────── #
    containers: list[Tag] = []
    seen_ids: set[int] = set()

    for anchor in anchors:
        node = _walk_up(anchor)
        if id(node) in seen_ids:
            continue
        dominated = any(_is_ancestor(existing, node) for existing in containers)
        if not dominated:
            containers = [c for c in containers if not _is_ancestor(node, c)]
            seen_ids   = {id(c) for c in containers}
            containers.append(node)
            seen_ids.add(id(node))

    if debug:
        print(f"[TRIM] Containers: {len(containers)}")
        for c in containers:
            print(f"  <{c.name}> id={c.get('id')!r} class={str(c.get('class',''))[:60]}")

    # ── 4. Guarantee every in-scope select appears ───────────────────────── #
    for el in soup.find_all("select"):
        if not isinstance(el, Tag):
            continue
        if not _in_scope(el):
            continue
        if _in_noise_section(el):
            continue
        if not any(_is_ancestor(c, el) or c is el for c in containers):
            node = _walk_up(el)
            if id(node) not in seen_ids:
                containers.append(node)
                seen_ids.add(id(node))
                if debug:
                    print(f"[TRIM] Force-added select container: "
                          f"<{node.name}> id={node.get('id')!r}")

    # ── 5. Sort in DOM order and serialise ───────────────────────────────── #
    tag_order   = {id(t): i for i, t in enumerate(soup.find_all(True))}
    containers.sort(key=lambda c: tag_order.get(id(c), 0))

    chunks  = [_serialise(c) for c in containers]
    trimmed = "\n\n".join(chunks)

    # ── 6. Clean whitespace and cap ──────────────────────────────────────── #
    trimmed = re.sub(r"\n{3,}", "\n\n", trimmed)
    trimmed = re.sub(r"[ \t]+", " ", trimmed)
    trimmed = trimmed.strip()

    if len(trimmed) > max_chars:
        trimmed = trimmed[:max_chars] + "\n<!-- trimmed: exceeded max_chars -->"

    if debug:
        print(f"[TRIM] {len(html):,} chars → {len(trimmed):,} chars  "
              f"({100 - 100*len(trimmed)//len(html)}% reduction)")

    return trimmed


# ── Playwright convenience wrapper ───────────────────────────────────────── #

def trim_page_html(page, extra_keywords=None, debug=False) -> str:
    """Call page.content() and trim. Use inside scraping functions."""
    return trim_html(page.content(), extra_keywords=extra_keywords, debug=debug)


# ── CLI ───────────────────────────────────────────────────────────────────── #

if __name__ == "__main__":
    import sys, pathlib
    if len(sys.argv) < 2:
        print("Usage: python html_trimmer.py <page.html>")
        sys.exit(1)
    raw = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
    result = trim_html(raw, debug=True)
    out = pathlib.Path(sys.argv[1]).with_suffix(".trimmed.html")
    out.write_text(result, encoding="utf-8")
    print(f"Written to {out}")
    print(result[:4000])
"""
Shared XPath builder utility.

Used by both InputValidator (for form inputs) and ScreenshotAnalyzer (for price elements)
so the XPath priority logic stays in one place.

Priority order: id > name+type > name > class_name > tag fallback.
"""


def build_xpath(
    tag: str = "*",
    id_: str = "",
    name: str = "",
    type_: str = "",
    class_name: str = "",
) -> str:
    """
    Build an XPath selector using the most specific available attribute.

    Args:
        tag:        HTML tag name (e.g. "span", "div"). Falls back to "*" if empty.
        id_:        Element id attribute value.
        name:       Element name attribute value.
        type_:      Element type attribute value (used together with name).
        class_name: Full class attribute string (space-separated classes are fine).

    Returns:
        XPath string that uniquely (or as specifically as possible) targets the element.
    """
    tag = tag or "*"

    if id_:
        return f"//*[@id='{id_}']"

    if name and type_:
        return f"//{tag}[@name='{name}' and @type='{type_}']"

    if name:
        return f"//{tag}[@name='{name}']"

    if class_name:
        return f"//{tag}[contains(@class, '{class_name}')]"

    return f"//{tag}"

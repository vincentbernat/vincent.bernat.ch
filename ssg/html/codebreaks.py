"""Allow line breaks inside inline code, before some punctuation marks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .dom import localname, select

if TYPE_CHECKING:
    import lxml.etree

MARKS = "._/="
MINIMUM = 3  # Minimum length of each part around a break


def cuts(text: str) -> list[int]:
    """Positions where a break is allowed."""
    result: list[int] = []
    last = 0
    for i in range(MINIMUM, len(text) - MINIMUM + 1):
        # Before a mark
        if text[i] not in MARKS or text[i - 1] in MARKS:
            continue
        # But not between two digits
        if text[i - 1].isdigit() and text[i + 1].isdigit():
            continue
        # And not if previous one is too close
        if i - last < MINIMUM:
            continue
        result.append(i)
        last = i
    return result


def split(el: lxml.etree._Element, text: str, after: bool) -> None:
    """Put text with <wbr> elements in the text of el, or after el."""
    positions = cuts(text)
    if not positions:
        return
    parts = [text[a:b] for a, b in zip([0, *positions], [*positions, len(text)])]
    if after:
        el.tail = parts[0]
        anchor = el
        for part in parts[1:]:
            wbr = el.makeelement("wbr", {})
            wbr.tail = part
            anchor.addnext(wbr)
            anchor = wbr
    else:
        el.text = parts[0]
        for i, part in enumerate(parts[1:]):
            wbr = el.makeelement("wbr", {})
            wbr.tail = part
            el.insert(i, wbr)


def fix(root: lxml.etree._Element) -> None:
    """Add <wbr> elements in code elements of .lf-text, outside of pre."""
    for code in select(root, ".lf-text code"):
        if any(localname(parent) == "pre" for parent in code.iterancestors()):
            continue
        for el in [code, *code.iterdescendants()]:
            if el is not code and el.tail:
                split(el, el.tail, True)
            if isinstance(el.tag, str) and el.text:
                split(el, el.text, False)

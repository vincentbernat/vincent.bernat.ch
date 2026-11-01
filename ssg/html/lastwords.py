"""Keep the last two words of paragraphs together and without hyphens."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .dom import INLINE_TAGS, WHITESPACE, localname, select

if TYPE_CHECKING:
    import lxml.etree

WORDS_CLASS = "lf-last-words"
SPACE_CLASS = "lf-last-space"
SHORT = 8  # Longer last words are not joined with the previous one

# A place holding text: the text of an element ("text") or the text after it
# ("tail").
Slot = tuple["lxml.etree._Element", str]


def slots(el: lxml.etree._Element) -> list[Slot] | None:
    """Text slots of an element in document order, without hidden elements.
    None when it contains an element that is not inline."""
    result: list[Slot] = [(el, "text")]
    for child in el:
        if isinstance(child.tag, str):
            if localname(child) not in INLINE_TAGS:
                return None
            if "hidden" not in child.attrib:
                inner = slots(child)
                if inner is None:
                    return None
                result.extend(inner)
        result.append((child, "tail"))
    return result


def get(slot: Slot) -> str:
    el, attr = slot
    return (el.text if attr == "text" else el.tail) or ""


def put(slot: Slot, value: str | None) -> None:
    el, attr = slot
    if attr == "text":
        el.text = value
    else:
        el.tail = value


def find(texts: list[str]) -> tuple[int, int, int, int] | None:
    """Start of the second to last word and of the last word, as slot
    indexes and offsets."""
    starts: list[tuple[int, int]] = []
    in_word = False
    for i in range(len(texts) - 1, -1, -1):
        t = texts[i]
        for j in range(len(t) - 1, -1, -1):
            if WHITESPACE.match(t[j]) is None:
                in_word = True
            elif in_word:
                starts.append((i, j + 1))
                in_word = False
                if len(starts) == 2:
                    return (*starts[1], *starts[0])
    if len(starts) == 1 and in_word:
        return (0, 0, *starts[0])
    return None


def place(slot: Slot, items: list[str | lxml.etree._Element]) -> None:
    """Replace the text of a slot with text and elements."""
    text = ""
    nodes: list[lxml.etree._Element] = []
    for item in items:
        if isinstance(item, str):
            if nodes:
                nodes[-1].tail = (nodes[-1].tail or "") + item
            else:
                text += item
        else:
            nodes.append(item)
    put(slot, text or None)
    el, attr = slot
    for i, node in enumerate(nodes):
        if attr == "text":
            el.insert(i, node)
        else:
            (nodes[i - 1] if i else el).addnext(node)


def join(block: lxml.etree._Element, found: list[Slot], i: int, offset: int) -> None:
    """Put the first space after a position in a span. Other slots holding
    the same space lose it."""
    seen = False
    for k in range(i, len(found)):
        t = get(found[k])
        if not seen:
            m = WHITESPACE.search(t, offset if k == i else 0)
            if m is None:
                continue
            span = block.makeelement("span", {"class": SPACE_CLASS})
            span.text = " "
            place(found[k], [t[: m.start()], span, t[m.end() :]])
            if m.end() < len(t):
                return
            seen = True
        else:
            m = WHITESPACE.match(t)
            rest = t[m.end() :] if m else t
            put(found[k], rest or None)
            if rest:
                return


def wrap(block: lxml.etree._Element, slot: Slot, offset: int) -> None:
    """Put the end of a block in a span, from a position. When the position
    is inside a child, the span starts before this child."""
    el, attr = slot
    if el is block:
        k = -1
    elif attr == "tail" and el.getparent() is block:
        k = block.index(el)
    else:
        while (parent := el.getparent()) is not block:
            assert parent is not None
            el = parent
        k = block.index(el) - 1
        offset = -1
    before = (block.text if k < 0 else block[k].tail) or ""
    if offset < 0:
        offset = len(before)
    span = block.makeelement("span", {"class": WORDS_CLASS})
    span.text = before[offset:] or None
    for child in list(block)[k + 1 :]:
        span.append(child)
    if k < 0:
        block.text = before[:offset] or None
    else:
        block[k].tail = before[:offset] or None
    block.append(span)


def fix(root: lxml.etree._Element) -> None:
    """Put the last two words of each paragraph of .lf-text in a span. When
    the last word is short, put the space between them in another span. CSS
    uses them to keep both words together and without hyphens. Otherwise,
    only put the last word in a span."""
    for block in select(root, ".lf-text p, .lf-text li, .lf-text dd"):
        found = slots(block)
        if found is None:
            continue
        texts = [get(slot) for slot in found]
        pos = find(texts)
        if pos is None:
            continue
        i, offset, last_i, last_offset = pos
        last = texts[last_i][last_offset:] + "".join(texts[last_i + 1 :])
        if len(last.strip()) <= SHORT:
            join(block, found, i, offset)
            wrap(block, found[i], offset)
        else:
            wrap(block, found[last_i], last_offset)

"""Typography: quotes, spaces, hyphens and line breaks."""

from __future__ import annotations

import dataclasses
import functools
import itertools
from typing import TYPE_CHECKING, Literal

import pyphen

from . import ctypography
from .dom import INLINE_TAGS, classes, localname, select

if TYPE_CHECKING:
    import lxml.etree

NBSP = "\u00a0"  # NO-BREAK SPACE
ZWSP = "\u200b"  # ZERO WIDTH SPACE
BREAKING_SPACES = (
    "\u1680"  # OGHAM SPACE MARK
    "\u2000"  # EN QUAD
    "\u2001"  # EM QUAD
    "\u2002"  # EN SPACE
    "\u2003"  # EM SPACE
    "\u2004"  # THREE-PER-EM SPACE
    "\u2005"  # FOUR-PER-EM SPACE
    "\u2006"  # SIX-PER-EM SPACE
    "\u2008"  # PUNCTUATION SPACE
    "\u2009"  # THIN SPACE
    "\u200a"  # HAIR SPACE
    "\u205f"  # MEDIUM MATHEMATICAL SPACE
    "\u3000"  # IDEOGRAPHIC SPACE
)
NON_BREAKING_SPACES = (
    "\u2007"  # FIGURE SPACE
    "\u202f"  # NARROW NO-BREAK SPACE
)
source_spaces = str.maketrans(
    dict.fromkeys(map(ord, BREAKING_SPACES), " ")
    | dict.fromkeys(map(ord, NON_BREAKING_SPACES), NBSP)
)

# Elements whose text is kept as is. Except for pre, they are part of the
# text around them, like a word.
SKIPPED = frozenset({
    "pre", "samp", "code", "tt", "kbd", "script", "style", "math", "svg",
    "x-latex",
})  # fmt: skip
# Elements whose text is hyphenated, except in headings
HYPHENATED = frozenset({"p", "ul", "ol", "dl"})
HEADINGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})


# Hyphenation of names with capital letters inside, in any language. A
# trailing "s" is allowed.
NAMES = [
    "Java-Script", "Type-Script", "Click-House", "Goat-Counter", "Duck-DuckGo",
    "Cloud-Front", "Wire-Guard", "Think-Pad", "Track-Point", "Yubi-Key",
    "Pulse-Audio", "Postgre-SQL", "Lucas-Arts",
]  # fmt: skip
names = {
    n.replace("-", ""): tuple(itertools.accumulate(len(p) for p in n.split("-")[:-1]))
    for n in NAMES
}

CODE_MARKS = "._/=:"  # Line breaks in code are allowed after them
CODE_PART = 3  # Minimum length of each part around a break in code


@dataclasses.dataclass(frozen=True)
class Slot:
    """A place holding text: the text of an element or the text after it."""

    el: lxml.etree._Element
    attr: Literal["text", "tail"]

    def get(self) -> str:
        return getattr(self.el, self.attr) or ""

    def put(self, value: str | None) -> None:
        setattr(self.el, self.attr, value)


@functools.cache
def dictionary(lang: str) -> ctypography.Hyphenator | None:
    name = pyphen.language_fallback(lang)
    if name is None:
        return None
    if name == "en":
        # "en" alone is British English
        name = "en_US"
    # The Elements of Typographic Style, 2.4.1
    return ctypography.Hyphenator(pyphen.LANGUAGES[name], names, left=2, right=3)


def ignored(el: lxml.etree._Element) -> bool:
    """Whether the text of an element is left out of the text around it:
    hidden elements and footnote marks."""
    if "hidden" in el.attrib:
        return True
    if localname(el) != "sup":
        return False
    return el.get("id", "").startswith("fnref:") or (
        "lf-sidenote-refmark" in classes(el)
    )


def punctuate(container: lxml.etree._Element, hyphens: bool = False) -> None:
    """Fix quotes and spaces in the text of an element, outside of code. When
    hyphens is true, also add soft hyphens in paragraphs and lists."""
    run = ctypography.Run()

    def flush() -> None:
        nonlocal run
        text = run.text
        # Nothing to change with only ASCII spaces, like between blocks
        if text.strip(" \t\n\r"):
            # One char for one char, starts stay the same
            run.text = text.translate(source_spaces)
            run.smarten()
            run.space()
            run.hyphenate()
            run.write()
        run = ctypography.Run()

    def walk(el: lxml.etree._Element, lang: str | None, hyphenated: bool) -> None:
        if ignored(el):
            return
        name = localname(el)
        if name in SKIPPED:
            if name == "pre":
                flush()
            else:
                run.opaque()
            return
        # Blocks separate runs
        block = name not in INLINE_TAGS
        if block:
            flush()
        lang = el.get("lang") or lang
        hyphenated = (
            hyphens and (hyphenated or name in HYPHENATED) and name not in HEADINGS
        )
        d = dictionary(lang) if hyphenated and lang else None
        run.add(Slot(el, "text"), d)
        for child in el:
            if isinstance(child.tag, str):
                walk(child, lang, hyphenated)
            run.add(Slot(child, "tail"), d)
        if block:
            flush()

    lang = next(
        (a.get("lang") for a in container.iterancestors() if a.get("lang")), None
    )
    walk(container, lang, False)
    flush()


def inline_slots(el: lxml.etree._Element) -> list[Slot] | None:
    """Slots with the visible text of an element, in order. None when it
    contains an element that is not inline."""
    result = [Slot(el, "text")]
    for child in el:
        if isinstance(child.tag, str):
            if localname(child) not in INLINE_TAGS:
                return None
            if "hidden" not in child.attrib:
                inner = inline_slots(child)
                if inner is None:
                    return None
                result += inner
        result.append(Slot(child, "tail"))
    return result


def keep_last_line(block: lxml.etree._Element) -> None:
    """Remove line break opportunities at the end of a block, so the last
    line is not too short."""
    slots = inline_slots(block)
    if slots is None:
        return
    texts = [slot.get() for slot in slots]
    for slot, text, new in zip(slots, texts, ctypography.last_line(texts)):
        if new != text:
            slot.put(new or None)


def code_cuts(text: str) -> list[int]:
    """Positions in code where a break is allowed."""
    result: list[int] = []
    last = 0
    for i in range(CODE_PART, len(text) - CODE_PART + 1):
        # After a mark and before a letter or a digit
        if text[i - 1] not in CODE_MARKS or not text[i].isalnum():
            continue
        # But not between two digits
        if text[i - 2].isdigit() and text[i].isdigit():
            continue
        # And not if previous one is too close
        if i - last < CODE_PART:
            continue
        result.append(i)
        last = i
    return result


def code_split(text: str) -> str:
    """Add zero-width spaces in code text."""
    positions = code_cuts(text)
    parts = [text[a:b] for a, b in zip([0, *positions], [*positions, len(text)])]
    return ZWSP.join(parts)


def code_break(container: lxml.etree._Element) -> None:
    """Add zero-width spaces in code elements, outside of pre."""
    for code in select(container, "code"):
        if any(localname(parent) == "pre" for parent in code.iterancestors()):
            continue
        for el in [code, *code.iterdescendants()]:
            if el is not code and el.tail:
                el.tail = code_split(el.tail)
            if isinstance(el.tag, str) and el.text:
                el.text = code_split(el.text)


def fix(root: lxml.etree._Element) -> None:
    """Fix typography in .lf-text and in the title of the article."""
    containers = select(root, ".lf-text, article > header > h1")
    for container in containers:
        if any(a in containers for a in container.iterancestors()):
            continue
        punctuate(container, hyphens=True)
        code_break(container)
        for block in select(container, "p, li, dd"):
            keep_last_line(block)

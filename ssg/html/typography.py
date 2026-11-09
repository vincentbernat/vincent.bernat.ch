"""Typography: quotes, spaces, hyphens and line breaks."""

from __future__ import annotations

import bisect
import dataclasses
import functools
import itertools
import re
import unicodedata
from typing import TYPE_CHECKING, Literal

import pyphen

from .dom import INLINE_TAGS, WHITESPACE, classes, localname, select

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    import lxml.etree

OBJECT = "\ufffc"  # OBJECT REPLACEMENT CHARACTER
NBSP = "\u00a0"  # NO-BREAK SPACE
NNBSP = "\u202f"  # NARROW NO-BREAK SPACE
SHY = "\u00ad"  # SOFT HYPHEN
ZWSP = "\u200b"  # ZERO WIDTH SPACE
ZWJ = "\u200d"  # ZERO WIDTH JOINER
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

LAST_LINE = 8  # Minimum length of the last line of a paragraph

# Units after a figure, separated by a normal space. Units with one letter
# are often found in text, so they need a no-break space.
UNITS = [
    "KB", "MB", "GB", "TB", "KiB", "MiB", "GiB", "TiB",
    "Ko", "Mo", "Go", "To", "Kio", "Mio", "Gio", "Tio",
    "Kbps", "Mbps", "Gbps", "Tbps", "Kb/s", "Mb/s", "Gb/s", "Tb/s",
    "Hz", "kHz", "MHz", "GHz",
    "ns", "µs", "ms",
    "nm", "mm", "cm", "km", "mi", "kg",
    "W", "mW", "kW", "dB", "dBm", "°C",
    "€", "$",
]  # fmt: skip

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

# Patterns for a run. When a pattern has groups, only the first one is
# replaced.
# A quote is opening at the start, after a space, a bracket or another
# opening quote, and before a non-space character. After a dash, it needs a
# letter after it.
opening_quote = re.compile(r"(?:(?<![^\s(\[{“‘«])|(?<=[—–])(?=.\w))['\"](?!\s)")
closing_quote = re.compile(r"['\"]")
decade = re.compile(r"(?<!\S)'(?=\d\ds)")  # '80s
ellipsis = re.compile(r"\.\.\.")
space_before_punct = re.compile(r"\s(?=[:;!?%»])")
space_after_punct = re.compile(r"(?<=«)\s")
space_between_figures = re.compile(r"(?<=[0-9])\s(?=[0-9]+(?:\W|$))")
version_number = re.compile(r"\b[A-Z][a-zA-Z]+(\s)(?=[0-9]+(?:\W|$))")
known_unit = re.compile(
    rf"\b[0-9]+(?:[,.][0-9]+)*([ \u00a0])(?=(?:{'|'.join(map(re.escape, UNITS))})(?!\w))"
)
# Cheating, the no-break space is already here
unknown_unit = re.compile(r"\b[0-9,.]+(\u00a0)(?=\w)")
chunk = re.compile(r"\S+")
url = re.compile(r"[/@]|\w\.\w")
word = re.compile(r"\b[^\W\d_]{5,}\b")


@dataclasses.dataclass(frozen=True)
class Slot:
    """A place holding text: the text of an element or the text after it."""

    el: lxml.etree._Element
    attr: Literal["text", "tail"]

    def get(self) -> str:
        return getattr(self.el, self.attr) or ""

    def put(self, value: str | None) -> None:
        setattr(self.el, self.attr, value)


class Run:
    """Text of several slots as one string, so patterns work across inline
    elements. OBJECT stands for an element whose text is not part of the
    run. write() puts the result back in the slots.

    The chars of a slot are next to each other. starts has the position of
    the first char of each slot. For <p>Say <em>"yes</em>" now</p>, the
    slots are p.text, em.text and em.tail:

        text    S a y ␣ " y e s " ␣ n o w
        starts  0       4       8

    """

    def __init__(self) -> None:
        self.slots: list[Slot] = []
        self.dictionaries: list[pyphen.Pyphen | None] = []  # for hyphenation
        self.chars: list[str] = []
        self.starts: list[int] = []

    def add(self, slot: Slot, d: pyphen.Pyphen | None = None) -> None:
        """Add the text of a slot at the end. d is the dictionary for the
        hyphenation of this text. An empty slot is not added.

        In the example, the run is built with:

            run.add(Slot(p, "text"))
            run.add(Slot(em, "text"))
            run.add(Slot(em, "tail"))

        """
        text = slot.get()
        if not text:
            return
        self.starts.append(len(self.chars))
        self.chars += text
        self.slots.append(slot)
        self.dictionaries.append(d)

    def opaque(self) -> None:
        """Add an element whose text is kept as is, like <code>. It becomes
        one OBJECT char, inside the slot before it. write() drops it.
        Patterns see it as a word but cannot change it.

            <p>Run <code>ls</code>.</p>

            text    R u n ␣ ￼ .
            starts  0         5

        """
        self.chars.append(OBJECT)

    @property
    def text(self) -> str:
        """The text of the run, for patterns. A position in this string is
        also a position in chars."""
        return "".join(self.chars)

    def owner(self, i: int) -> int:
        """Slot of the char at i."""
        return bisect.bisect_right(self.starts, i) - 1

    def edit(self, changes: Iterable[tuple[int, int, str]]) -> None:
        """Replace spans of the text, in order and without overlap. The new
        text goes to the slot of the first replaced char. An insertion goes
        to the slot of the char before it, unless this char is OBJECT. Spans
        with OBJECT are not changed.

        In the example, (3, 4, "_") and (8, 8, "!") give:

            text    S a y _ " y e s ! " ␣ n o w
            starts  0       4         9

        """
        chars: list[str] = []
        starts: list[int] = []
        last = k = 0
        for start, end, value in changes:
            first = start if start < end else start - 1
            if OBJECT in self.chars[first:end]:
                continue
            chars += self.chars[last:start]
            # Slots starting up to the first char keep their place, the
            # next ones up to the end of the span start after the new text
            while k < len(self.starts) and self.starts[k] <= first:
                starts.append(self.starts[k] + len(chars) - start)
                k += 1
            chars += value
            while k < len(self.starts) and self.starts[k] <= end:
                starts.append(len(chars))
                k += 1
            last = end
        if not last and not chars:
            return
        starts += [s + len(chars) - last for s in self.starts[k:]]
        self.chars = chars + self.chars[last:]
        self.starts = starts

    def sub(
        self, pattern: re.Pattern[str], repl: str | Callable[[re.Match[str]], str]
    ) -> None:
        """Replace matches of a pattern, or their first group, with edit().
        repl is a string or a function returning a string from a match.
        Groups are used when the part to replace needs a lookbehind with a
        variable width. In the example:

            run.sub(re.compile(r"(?<=\\w)\\""), "”")

        """
        changes = []
        for m in pattern.finditer(self.text):
            start, end = m.span(1) if pattern.groups else m.span()
            changes.append((start, end, repl if isinstance(repl, str) else repl(m)))
        self.edit(changes)

    def write(self) -> None:
        """Put the chars back in their slots, using starts. OBJECT chars are
        dropped. Only slots with a different text are changed. A slot left
        empty becomes None. In the example:

            p.text   "Say "
            em.text  "“yes"
            em.tail  "” now"

        """
        for slot, start, end in zip(
            self.slots, self.starts, [*self.starts[1:], len(self.chars)]
        ):
            text = "".join(self.chars[start:end]).replace(OBJECT, "")
            if text != slot.get():
                slot.put(text or None)


def smarten(run: Run) -> None:
    """Quotes and ellipses."""
    text = run.text
    if "'" in text or '"' in text:
        run.sub(decade, "’")
        run.sub(opening_quote, lambda m: "‘" if m[0] == "'" else "“")
        run.sub(closing_quote, lambda m: "’" if m[0] == "'" else "”")
    if "..." in text:
        run.sub(ellipsis, "…")


def space(run: Run) -> None:
    """French punctuation and figures."""
    # A pattern turns a space into NNBSP. This cannot create a match for
    # another one, so the text is searched once.
    text = run.text
    for pattern in (
        space_before_punct,
        space_after_punct,
        space_between_figures,
        version_number,
        known_unit,
        unknown_unit,
    ):
        if pattern.search(text):
            run.sub(pattern, NNBSP)


@functools.cache
def dictionary(lang: str) -> pyphen.Pyphen | None:
    name = pyphen.language_fallback(lang)
    if name is None:
        return None
    if name == "en":
        # "en" alone is British English
        name = "en_US"
    # The Elements of Typographic Style, 2.4.1
    return pyphen.Pyphen(lang=name, left=2, right=3)


@functools.cache
def hyphen_positions(w: str, d: pyphen.Pyphen) -> tuple[int, ...]:
    """Positions of soft hyphens in a word. Words with a capital letter after
    the first one have none, unless they are in NAMES."""
    if w in names:
        return names[w]
    if w.endswith("s") and w[:-1] in names:
        return names[w[:-1]]
    if any(c.isupper() for c in w[1:]):
        return ()
    return tuple(p for p in d.positions(w) if p.data is None)


def hyphenate(run: Run) -> None:
    """Add soft hyphens in words of hyphenated slots, except in URLs."""
    if all(d is None for d in run.dictionaries):
        return
    text = run.text
    changes: list[tuple[int, int, str]] = []
    for c in chunk.finditer(text):
        if url.search(c[0]):
            continue
        for m in word.finditer(text, c.start(), c.end()):
            d = run.dictionaries[run.owner(m.start())]
            if d is not None:
                changes += [
                    (m.start() + p, m.start() + p, SHY)
                    for p in hyphen_positions(m[0], d)
                ]
    run.edit(changes)


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
    run = Run()

    def flush() -> None:
        nonlocal run
        text = run.text
        # Nothing to change with only ASCII spaces, like between blocks
        if text.strip(" \t\n\r"):
            # One char for one char, starts stay the same
            run.chars = list(text.translate(source_spaces))
            smarten(run)
            space(run)
            hyphenate(run)
            run.write()
        run = Run()

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


def inline_run(el: lxml.etree._Element) -> Run | None:
    """Run with the visible text of an element. None when it contains an
    element that is not inline."""
    run = Run()

    def walk(el: lxml.etree._Element) -> bool:
        run.add(Slot(el, "text"))
        for child in el:
            if isinstance(child.tag, str):
                if localname(child) not in INLINE_TAGS:
                    return False
                if "hidden" not in child.attrib and not walk(child):
                    return False
            run.add(Slot(child, "tail"))
        return True

    return run if walk(el) else None


def joined(chars: list[str], j: int) -> bool:
    """Whether chars[j] belongs to the grapheme cluster of the character
    before it. This is an approximation: marks, format characters, skin
    tones and characters after a ZWJ."""
    c = chars[j]
    if unicodedata.category(c) in ("Mn", "Mc", "Me", "Cf"):
        return True
    if "\U0001f3fb" <= c <= "\U0001f3ff":
        return True
    return j > 0 and chars[j - 1] == ZWJ


def keep_last_line(block: lxml.etree._Element) -> None:
    """Remove line break opportunities at the end of a block, so the last
    line has at least LAST_LINE grapheme clusters. Spaces become no-break
    spaces. Soft hyphens and zero-width spaces are removed."""
    run = inline_run(block)
    if run is None:
        return
    chars = run.chars
    count = 0
    spaces: list[int] = []
    for j in range(len(chars) - 1, -1, -1):
        if count >= LAST_LINE:
            break
        c = chars[j]
        if c in (SHY, ZWSP):
            chars[j] = ""
        elif WHITESPACE.match(c):
            if count:
                spaces.append(j)
        else:
            # Spaces between two words: keep one, as a no-break space
            if spaces:
                for s in spaces:
                    chars[s] = ""
                chars[spaces[-1]] = NBSP
                spaces = []
            if not c.isspace() and not joined(chars, j):
                count += 1
    run.write()


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

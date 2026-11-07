"""Typography: quotes, spaces, hyphens and line breaks."""

from __future__ import annotations

import functools
import re
from typing import TYPE_CHECKING

import pyphen

from .dom import INLINE_TAGS, WHITESPACE, localname, select

if TYPE_CHECKING:
    import lxml.etree

NBSP = "\u00a0"
NNBSP = "\u202f"
SHY = "\u00ad"
ZWSP = "\u200b"

# Elements whose text is kept as is
SKIPPED = frozenset({
    "pre", "samp", "code", "tt", "kbd", "script", "style", "math", "svg",
    "x-latex",
})  # fmt: skip
# Elements whose text is hyphenated, except in headings
HYPHENATED = frozenset({"p", "ul", "ol", "dl"})
HEADINGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})

LAST_LINE = 8  # Minimum length of the last line of a paragraph
CODE_MARKS = "._/=:"  # Line breaks in code are allowed after them
CODE_PART = 3  # Minimum length of each part around a break in code
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
names = {n.replace("-", ""): n.replace("-", SHY) for n in NAMES}

# A quote is opening after a space, a bracket or another opening quote, and
# before a non-space character. After a dash, it needs a letter after it.
opening_quote = re.compile(r"(?:(?<=[\s(\[{“‘«])|(?<=[—–])(?=.\w))(['\"])(?!\s)")
decade = re.compile(r"(?<=\s)'(?=\d\ds)")  # '80s
space_before_punct = re.compile(r"\s([:;!?%»])")
space_after_punct = re.compile(r"«\s")
space_between_figures = re.compile(r"([0-9]|^)\s([0-9]+(?:\W|$))")
version_number = re.compile(r"(\b[A-Z][a-zA-Z]+)\s([0-9]+(?:\W|$))")
known_unit = re.compile(
    rf"(\b[0-9]+(?:[,.][0-9]+)*)[ \u00a0]({'|'.join(map(re.escape, UNITS))})(?!\w)"
)
# Cheating, the no-break space is already here
unknown_unit = re.compile(r"(\b[0-9,.]+)\u00a0(\w)")
chunk = re.compile(r"\S+")
url = re.compile(r"[/@]|\w\.\w")
word = re.compile(r"\b[^\W\d_]{5,}\b")

# A place holding text: the text of an element ("text") or the text after it
# ("tail").
Slot = tuple["lxml.etree._Element", str]


def get(slot: Slot) -> str:
    el, attr = slot
    return (el.text if attr == "text" else el.tail) or ""


def put(slot: Slot, value: str | None) -> None:
    el, attr = slot
    if attr == "text":
        el.text = value
    else:
        el.tail = value


def smarten(text: str, previous: str) -> str:
    """Quotes and ellipses. previous is the character before the text."""
    if "'" in text or '"' in text:
        text = decade.sub("’", previous + text)
        text = opening_quote.sub(lambda m: "‘" if m[1] == "'" else "“", text)
        text = text.replace("'", "’").replace('"', "”")[1:]
    return text.replace("...", "…")


def space(text: str) -> str:
    """French punctuation and figures."""
    text = space_before_punct.sub(NNBSP + r"\1", text)
    text = space_after_punct.sub("«" + NNBSP, text)
    text = space_between_figures.sub(r"\1" + NNBSP + r"\2", text)
    text = version_number.sub(r"\1" + NNBSP + r"\2", text)
    text = known_unit.sub(r"\1" + NNBSP + r"\2", text)
    return unknown_unit.sub(r"\1" + NNBSP + r"\2", text)


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


def hyphenate(text: str, lang: str | None) -> str:
    """Add soft hyphens in words. URLs and words with a capital letter after
    the first one are not changed, unless they are in NAMES."""
    d = dictionary(lang) if lang else None
    if d is None:
        return text

    def insert(m: re.Match[str]) -> str:
        w = m.group()
        if w in names:
            return names[w]
        if w.endswith("s") and w[:-1] in names:
            return names[w[:-1]] + "s"
        if any(c.isupper() for c in w[1:]):
            return w
        positions = [p for p in d.positions(w) if p.data is None]
        parts = [w[a:b] for a, b in zip([0, *positions], [*positions, len(w)])]
        return SHY.join(parts)

    def split(m: re.Match[str]) -> str:
        c = m.group()
        if url.search(c):
            return c
        return word.sub(insert, c)

    return chunk.sub(split, text)


def punctuate(container: lxml.etree._Element, hyphens: bool = False) -> None:
    """Fix quotes and spaces in the text of an element, outside of code. When
    hyphens is true, also add soft hyphens in paragraphs and lists."""
    previous = " "

    def visit(slot: Slot, lang: str | None, hyphenated: bool) -> None:
        nonlocal previous
        original = get(slot)
        if not original:
            return
        text = space(smarten(original, previous))
        if hyphenated:
            text = hyphenate(text, lang)
        put(slot, text)
        previous = original[-1]

    def walk(el: lxml.etree._Element, lang: str | None, hyphenated: bool) -> None:
        nonlocal previous
        name = localname(el)
        # Blocks separate words like a space
        block = name not in INLINE_TAGS
        if name in SKIPPED:
            # Text inside is kept as is, only its last character is needed
            last = "".join(el.itertext())[-1:]
            previous = " " if block else (last or previous)
            return
        if block:
            previous = " "
        lang = el.get("lang") or lang
        hyphenated = (
            hyphens and (hyphenated or name in HYPHENATED) and name not in HEADINGS
        )
        visit((el, "text"), lang, hyphenated)
        for child in el:
            if isinstance(child.tag, str):
                walk(child, lang, hyphenated)
            visit((child, "tail"), lang, hyphenated)
        if block:
            previous = " "

    lang = next(
        (a.get("lang") for a in container.iterancestors() if a.get("lang")), None
    )
    walk(container, lang, False)


def cuts(text: str) -> list[int]:
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


def split(text: str) -> str:
    """Add zero-width spaces in code text."""
    positions = cuts(text)
    parts = [text[a:b] for a, b in zip([0, *positions], [*positions, len(text)])]
    return ZWSP.join(parts)


def break_code(container: lxml.etree._Element) -> None:
    """Add zero-width spaces in code elements, outside of pre."""
    for code in select(container, "code"):
        if any(localname(parent) == "pre" for parent in code.iterancestors()):
            continue
        for el in [code, *code.iterdescendants()]:
            if el is not code and el.tail:
                el.tail = split(el.tail)
            if isinstance(el.tag, str) and el.text:
                el.text = split(el.text)


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


def keep_last_line(block: lxml.etree._Element) -> None:
    """Remove line break opportunities at the end of a block, so the last
    line has at least LAST_LINE characters. Spaces become no-break spaces.
    Soft hyphens and zero-width spaces are removed."""
    found = slots(block)
    if found is None:
        return
    texts = [list(get(slot)) for slot in found]
    count = 0
    spaces: list[tuple[int, int]] = []
    for k in range(len(found) - 1, -1, -1):
        if count >= LAST_LINE:
            break
        chars = texts[k]
        for j in range(len(chars) - 1, -1, -1):
            if count >= LAST_LINE:
                break
            c = chars[j]
            if c in (SHY, ZWSP):
                chars[j] = ""
            elif WHITESPACE.match(c):
                if count:
                    spaces.append((k, j))
            else:
                # Spaces between two words: keep one, as a no-break space
                if spaces:
                    for sk, sj in spaces:
                        texts[sk][sj] = ""
                    sk, sj = spaces[-1]
                    texts[sk][sj] = NBSP
                    spaces = []
                if not c.isspace():
                    count += 1
    for slot, chars in zip(found, texts):
        text = "".join(chars)
        if text != get(slot):
            put(slot, text or None)


def fix(root: lxml.etree._Element) -> None:
    """Fix typography in .lf-text and in the title of the article."""
    containers = select(root, ".lf-text, article > header > h1")
    for container in containers:
        if any(a in containers for a in container.iterancestors()):
            continue
        punctuate(container, hyphens=True)
        break_code(container)
        for block in select(container, "p, li, dd"):
            keep_last_line(block)

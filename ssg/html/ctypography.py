# cython: language_level=3
"""Typography helpers, compiled with Cython in pure Python mode."""

import unicodedata

import cython
import pyphen

cython.declare(
    NBSP=cython.Py_UCS4, SHY=cython.Py_UCS4, ZWSP=cython.Py_UCS4, ZWJ=cython.Py_UCS4
)
OBJECT = "\ufffc"  # OBJECT REPLACEMENT CHARACTER
NNBSP = "\u202f"  # NARROW NO-BREAK SPACE
NBSP = "\u00a0"  # NO-BREAK SPACE
SHY = "\u00ad"  # SOFT HYPHEN
ZWSP = "\u200b"  # ZERO WIDTH SPACE
ZWJ = "\u200d"  # ZERO WIDTH JOINER


@cython.cfunc
@cython.inline
def is_word(c: cython.Py_UCS4) -> cython.bint:
    """Same as \\w in Python regular expressions."""
    return c.isalnum() or c == "_"


@cython.cfunc
@cython.inline
def is_letter(c: cython.Py_UCS4) -> cython.bint:
    """Same as [^\\W\\d_] in Python regular expressions."""
    return c.isalnum() and not c.isdecimal() and c != "_"


@cython.cclass
class Hyphenator:
    """Hyphenation of words with the patterns of a pyphen dictionary (Liang's
    algorithm). Positions are cached for each word."""

    patterns: dict  # pattern -> (offset, values)
    maxlen: cython.Py_ssize_t
    left: cython.Py_ssize_t
    right: cython.Py_ssize_t
    names: dict
    cache: dict

    def __init__(
        self, path, names: dict, left: cython.Py_ssize_t, right: cython.Py_ssize_t
    ) -> None:
        """path is the path of a pyphen dictionary. names has the positions
        of soft hyphens for some words, in any language. left and right are
        the minimum number of characters before the first hyphen and after
        the last one."""
        hd = pyphen.HyphDict(path)
        for _, values in hd.patterns.values():
            if any(getattr(v, "data", None) is not None for v in values):
                raise ValueError(f"nonstandard hyphenation in {path}")
        self.patterns = hd.patterns
        self.maxlen = hd.maxlen
        self.left = left
        self.right = right
        self.names = names
        self.cache = {}

    @cython.cfunc
    def positions(self, word: str) -> tuple:
        """Positions of soft hyphens in a word. Words with a capital letter
        after the first one have none, unless they are in names."""
        result = self.cache.get(word)
        if result is not None:
            return cython.cast(tuple, result)
        if word in self.names:
            result = self.names[word]
        elif word.endswith("s") and word[: len(word) - 1] in self.names:
            result = self.names[word[: len(word) - 1]]
        elif any(c.isupper() for c in word[1:]):
            result = ()
        else:
            result = self.liang(word)
        self.cache[word] = result
        return cython.cast(tuple, result)

    @cython.cfunc
    def liang(self, word: str) -> tuple:
        """Positions of soft hyphens in a word, from the patterns."""
        pointed: str = "." + word.lower() + "."
        m: cython.Py_ssize_t = len(pointed)
        i: cython.Py_ssize_t
        j: cython.Py_ssize_t
        k: cython.Py_ssize_t
        offset: cython.Py_ssize_t
        stop: cython.Py_ssize_t
        right: cython.Py_ssize_t = len(word) - self.right
        references: list = [0] * (m + 1)
        for i in range(m - 1):
            stop = min(i + self.maxlen, m) + 1
            for j in range(i + 1, stop):
                pattern = self.patterns.get(pointed[i:j])
                if pattern is None:
                    continue
                offset, values = pattern
                for k, v in enumerate(values):
                    references[i + offset + k] = max(references[i + offset + k], v)
        return tuple(
            i - 1
            for i in range(m + 1)
            if references[i] % 2 and self.left <= i - 1 <= right
        )


@cython.cfunc
def hyphen_positions(text: str, starts: list, hyphenators: list) -> list:
    """Positions where soft hyphens go in the words of text, except in URLs.
    starts has the position of the first char of each slot and hyphenators the
    Hyphenator of each slot, or None."""
    n: cython.Py_ssize_t = len(text)
    slots: cython.Py_ssize_t = len(starts)
    i: cython.Py_ssize_t = 0
    j: cython.Py_ssize_t
    start: cython.Py_ssize_t
    word: cython.Py_ssize_t
    owner: cython.Py_ssize_t = 0
    c: cython.Py_UCS4
    url: cython.bint
    letters: cython.bint
    result: list = []
    while i < n:
        # A chunk is a sequence of non-space chars
        if text[i].isspace():
            i += 1
            continue
        start = i
        while i < n and not text[i].isspace():
            i += 1
        url = False
        for j in range(start, i):
            c = text[j]
            if (
                c == "/"
                or c == "@"
                or (
                    c == "."
                    and start < j < i - 1
                    and is_word(text[j - 1])
                    and is_word(text[j + 1])
                )
            ):
                url = True
                break
        if url:
            continue
        # A word is a sequence of letters, at least 5 of them
        j = start
        while j < i:
            if not is_word(text[j]):
                j += 1
                continue
            word = j
            letters = True
            while j < i and is_word(text[j]):
                letters = letters and is_letter(text[j])
                j += 1
            if not letters or j - word < 5:
                continue
            # Words come in order, so the slot only moves forward
            while (
                owner + 1 < slots
                and cython.cast(cython.Py_ssize_t, starts[owner + 1]) <= word
            ):
                owner += 1
            hyphenator = hyphenators[owner]
            if hyphenator is None:
                continue
            for p in cython.cast(Hyphenator, hyphenator).positions(text[word:j]):
                result.append(word + p)
    return result


# Units after a figure, separated by a normal space. Units with one letter
# are often found in text, so they need a no-break space.
UNITS = (
    "KB", "MB", "GB", "TB", "KiB", "MiB", "GiB", "TiB",
    "Ko", "Mo", "Go", "To", "Kio", "Mio", "Gio", "Tio",
    "Kbps", "Mbps", "Gbps", "Tbps", "Kb/s", "Mb/s", "Gb/s", "Tb/s",
    "Hz", "kHz", "MHz", "GHz",
    "ns", "µs", "ms",
    "nm", "mm", "cm", "km", "mi", "kg",
    "W", "mW", "kW", "dB", "dBm", "°C",
    "€", "$", "F", "FF", "CHF",
)  # fmt: skip


@cython.cfunc
@cython.inline
def is_figure(c: cython.Py_UCS4) -> cython.bint:
    """Same as [0-9] in Python regular expressions."""
    return "0" <= c <= "9"


@cython.cfunc
def boundary(text: str, i: cython.Py_ssize_t) -> cython.bint:
    """Whether there is a word boundary (\\b) before text[i]."""
    before: cython.bint = i > 0 and is_word(text[i - 1])
    after: cython.bint = i < len(text) and is_word(text[i])
    return before != after


@cython.cfunc
def figures_at(text: str, i: cython.Py_ssize_t) -> cython.bint:
    """Whether text[i:] starts with figures, followed by the end or by a char
    that is not part of a word."""
    j: cython.Py_ssize_t = i
    n: cython.Py_ssize_t = len(text)
    while j < n and is_figure(text[j]):
        j += 1
    return j > i and (j == n or not is_word(text[j]))


@cython.cfunc
def unit_at(text: str, i: cython.Py_ssize_t) -> cython.bint:
    """Whether text[i:] starts with a unit, not followed by a word char."""
    end: cython.Py_ssize_t
    n: cython.Py_ssize_t = len(text)
    for unit in UNITS:
        if text.startswith(unit, i):
            end = i + len(cython.cast(str, unit))
            if end == n or not is_word(text[end]):
                return True
    return False


@cython.cfunc
def narrow_space(text: str, i: cython.Py_ssize_t) -> cython.bint:
    """Whether the space at i becomes a narrow no-break space."""
    j: cython.Py_ssize_t
    start: cython.Py_ssize_t
    n: cython.Py_ssize_t = len(text)
    c: cython.Py_UCS4 = text[i]
    # Before some punctuation marks
    if i + 1 < n and text[i + 1] in ":;!?%»":
        return True
    # After an opening guillemet
    if i > 0 and text[i - 1] == "«":
        return True
    # Between figures, like "1 000"
    if figures_at(text, i + 1) and i > 0 and is_figure(text[i - 1]):
        return True
    # Known units, like "10 km"
    if c == " " or c == NBSP:
        start = i
        while start > 0 and is_figure(text[start - 1]):
            start -= 1
        if start < i and boundary(text, start) and unit_at(text, i + 1):
            return True
    # Other units, already with a no-break space in the source
    if c == NBSP and i + 1 < n and is_word(text[i + 1]):
        start = i
        while start > 0 and (is_figure(text[start - 1]) or text[start - 1] in ",."):
            start -= 1
        for j in range(start, i):
            if boundary(text, j):
                return True
    return False


@cython.cfunc
def version_space(text: str, i: cython.Py_ssize_t) -> cython.bint:
    """Whether the space at i is in a version number, like "Python 3", and
    becomes a no-break space."""
    j: cython.Py_ssize_t
    start: cython.Py_ssize_t
    if not figures_at(text, i + 1):
        return False
    start = i
    while start > 0 and is_word(text[start - 1]):
        start -= 1
    if i - start < 2 or not "A" <= text[start] <= "Z":
        return False
    for j in range(start + 1, i):
        if not ("a" <= text[j] <= "z" or "A" <= text[j] <= "Z"):
            return False
    return True


@cython.cclass
class Run:
    """Text of several slots as one string, so patterns work across inline
    elements. OBJECT stands for an element whose text is not part of the run.
    write() puts the result back in the slots.

    The chars of a slot are next to each other. starts has the position of the
    first char of each slot. For <p>Say <em>"yes</em>" now</p>, the slots are
    p.text, em.text and em.tail:

        text    S a y ␣ " y e s " ␣ n o w
        starts  0       4       8

    """

    slots = cython.declare(list, visibility="public")
    hyphenators = cython.declare(list, visibility="public")  # for each slot, or None
    starts = cython.declare(list, visibility="public")
    text = cython.declare(str, visibility="public")

    def __init__(self) -> None:
        self.slots = []
        self.hyphenators = []
        self.starts = []
        self.text = ""

    def add(self, slot, hyphenator: Hyphenator | None = None) -> None:
        """Add the text of a slot at the end. The hyphenator is used for this
        text. An empty slot is not added.

        In the example, the run is built with:

            run.add(Slot(p, "text"))
            run.add(Slot(em, "text"))
            run.add(Slot(em, "tail"))

        """
        text: str = slot.get()
        if not text:
            return
        self.starts.append(len(self.text))
        self.text += text
        self.slots.append(slot)
        self.hyphenators.append(hyphenator)

    def opaque(self) -> None:
        """Add an element whose text is kept as is, like <code>. It becomes one
        OBJECT char, inside the slot before it. write() drops it. Patterns see
        it as a word but cannot change it.

            <p>Run <code>ls</code>.</p>

            text    R u n ␣ OBJECT .
            starts  0              5

        """
        self.text += OBJECT

    def edit(self, changes: list) -> None:
        """Replace spans of the text, in order and without overlap. The new text
        goes to the slot of the first replaced char. An insertion goes to the
        slot of the char before it, unless this char is OBJECT. Spans with
        OBJECT are not changed.

        In the example, (3, 4, "_") and (8, 8, "!") give:

            text    S a y _ " y e s ! " ␣ n o w
            starts  0       4         9

        """
        text: str = self.text
        old: list = self.starts
        pieces: list = []
        starts: list = []
        last: cython.Py_ssize_t = 0
        k: cython.Py_ssize_t = 0
        n: cython.Py_ssize_t = len(old)
        length: cython.Py_ssize_t = 0
        start: cython.Py_ssize_t
        end: cython.Py_ssize_t
        first: cython.Py_ssize_t
        value: str
        for start, end, value in changes:
            first = start if start < end else start - 1
            if OBJECT in text[first:end]:
                continue
            pieces.append(text[last:start])
            # length is now the new position of start
            length += start - last
            # Slots starting up to the first char keep their place, the
            # next ones up to the end of the span start after the new text
            while k < n and cython.cast(cython.Py_ssize_t, old[k]) <= first:
                starts.append(cython.cast(cython.Py_ssize_t, old[k]) + length - start)
                k += 1
            pieces.append(value)
            length += len(value)
            while k < n and cython.cast(cython.Py_ssize_t, old[k]) <= end:
                starts.append(length)
                k += 1
            last = end
        if not pieces:
            return
        pieces.append(text[last:])
        while k < n:
            starts.append(cython.cast(cython.Py_ssize_t, old[k]) + length - last)
            k += 1
        self.text = "".join(pieces)
        self.starts = starts

    def smarten(self) -> None:
        """Quotes and ellipses."""
        text: str = self.text
        i: cython.Py_ssize_t
        n: cython.Py_ssize_t = len(text)
        c: cython.Py_UCS4
        before: cython.Py_UCS4
        changes: list
        if "'" in text or '"' in text:
            # '80s
            changes = []
            for i in range(n - 3):
                if (
                    text[i] == "'"
                    and (i == 0 or text[i - 1].isspace())
                    and text[i + 1].isdecimal()
                    and text[i + 2].isdecimal()
                    and text[i + 3] == "s"
                ):
                    changes.append((i, i + 1, "’"))
            self.edit(changes)
            # A quote is opening at the start, after a space, a bracket or
            # another opening quote, and before a non-space character. After
            # a dash, it needs a letter after it.
            text = self.text
            changes = []
            for i in range(n):
                c = text[i]
                if c != "'" and c != '"':
                    continue
                if i + 1 < n and text[i + 1].isspace():
                    continue
                if i > 0:
                    before = text[i - 1]
                    if not (
                        before.isspace()
                        or before in "([{“‘«"
                        or (before in "—–" and i + 1 < n and is_word(text[i + 1]))
                    ):
                        continue
                changes.append((i, i + 1, "‘" if c == "'" else "“"))
            self.edit(changes)
            # Other quotes are closing
            text = self.text
            changes = []
            for i in range(n):
                c = text[i]
                if c == "'" or c == '"':
                    changes.append((i, i + 1, "’" if c == "'" else "”"))
            self.edit(changes)
        text = self.text
        if "..." in text:
            changes = []
            i = 0
            n = len(text)
            while i + 3 <= n:
                if text[i] == "." and text[i + 1] == "." and text[i + 2] == ".":
                    changes.append((i, i + 3, "…"))
                    i += 3
                else:
                    i += 1
            self.edit(changes)

    def space(self) -> None:
        """French punctuation and figures. Some spaces become narrow no-break
        spaces, spaces in version numbers become no-break spaces. A rule only
        turns a space into a no-break space. This cannot create or remove a
        match for another rule, so all rules look at the same text.

        """
        text: str = self.text
        i: cython.Py_ssize_t
        changes: list = []
        for i in range(len(text)):
            if not text[i].isspace():
                continue
            if narrow_space(text, i):
                changes.append((i, i + 1, NNBSP))
            elif version_space(text, i):
                changes.append((i, i + 1, NBSP))
        self.edit(changes)

    def hyphenate(self) -> None:
        """Add soft hyphens in words of slots with a hyphenator, except in
        URLs.

        """
        if all(h is None for h in self.hyphenators):
            return
        self.edit(
            [
                (p, p, SHY)
                for p in hyphen_positions(self.text, self.starts, self.hyphenators)
            ]
        )

    def write(self) -> None:
        """Put the text back in the slots, using starts. OBJECT chars are
        dropped. Only slots with a different text are changed. A slot left empty
        becomes None. In the example:

            p.text   "Say "
            em.text  "“yes"
            em.tail  "” now"

        """
        k: cython.Py_ssize_t
        n: cython.Py_ssize_t = len(self.slots)
        start: cython.Py_ssize_t
        end: cython.Py_ssize_t
        text: str
        for k in range(n):
            start = self.starts[k]
            end = self.starts[k + 1] if k + 1 < n else len(self.text)
            text = self.text[start:end].replace(OBJECT, "")
            slot = self.slots[k]
            if text != slot.get():
                slot.put(text or None)


@cython.cfunc
def joined(c: cython.Py_UCS4, before: cython.Py_UCS4) -> cython.bint:
    """Whether c belongs to the grapheme cluster of the char before it. This
    is an approximation: marks, format chars, skin tones and chars after a
    ZWJ."""
    if before == ZWJ:
        return True
    if c < "\x80":
        return False
    if "\U0001f3fb" <= c <= "\U0001f3ff":
        return True
    return unicodedata.category(c) in ("Mn", "Mc", "Me", "Cf")


def last_line(texts: list, minimum: cython.Py_ssize_t) -> list:
    """Remove line break opportunities at the end of a block, so the last line
    has at least minimum grapheme clusters. Spaces become no-break spaces.
    Soft hyphens and zero-width spaces are removed. texts has the text of each
    slot of the block. Return the new text of each slot.

    """
    chars: list = list("".join(texts))
    spaces: list = []
    count: cython.Py_ssize_t = 0
    j: cython.Py_ssize_t
    start: cython.Py_ssize_t = 0
    c: cython.Py_UCS4
    before: cython.Py_UCS4
    for j in range(len(chars) - 1, -1, -1):
        if count >= minimum:
            break
        c = chars[j]
        if c == SHY or c == ZWSP:
            chars[j] = ""
        elif c in " \t\n\x0c\r":
            if count:
                spaces.append(j)
        else:
            # Spaces between two words: keep one, as a no-break space
            if spaces:
                for s in spaces:
                    chars[s] = ""
                chars[spaces[-1]] = NBSP
                spaces = []
            before = 0
            if j > 0:
                before = chars[j - 1]
            if not c.isspace() and not joined(c, before):
                count += 1
    result = []
    for text in texts:
        result.append("".join(chars[start : start + len(text)]))
        start += len(text)
    return result

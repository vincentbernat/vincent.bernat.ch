# cython: language_level=3
"""Typography helpers compiled with Cython."""

import unicodedata

import pyphen

OBJECT = "\ufffc"  # OBJECT REPLACEMENT CHARACTER
NNBSP = "\u202f"  # NARROW NO-BREAK SPACE
cdef Py_UCS4 NBSP = u"\u00a0"  # NO-BREAK SPACE
cdef Py_UCS4 SHY = u"\u00ad"  # SOFT HYPHEN
cdef Py_UCS4 ZWSP = u"\u200b"  # ZERO WIDTH SPACE
cdef Py_UCS4 ZWJ = u"\u200d"  # ZERO WIDTH JOINER

cdef Py_ssize_t LAST_LINE = 8  # Minimum length of the last line of a paragraph


cdef inline bint is_word(Py_UCS4 c):
    """Same as \\w in Python regular expressions."""
    return c.isalnum() or c == u"_"


cdef inline bint is_letter(Py_UCS4 c):
    """Same as [^\\W\\d_] in Python regular expressions."""
    return c.isalnum() and not c.isdecimal() and c != u"_"


cdef class Hyphenator:
    """Hyphenation of words with the patterns of a pyphen dictionary (Liang's
    algorithm). Positions are cached for each word."""

    cdef dict patterns  # pattern -> (offset, values)
    cdef Py_ssize_t maxlen
    cdef Py_ssize_t left
    cdef Py_ssize_t right
    cdef dict names
    cdef dict cache

    def __init__(self, path, dict names, Py_ssize_t left, Py_ssize_t right):
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

    cdef tuple positions(self, str word):
        """Positions of soft hyphens in a word. Words with a capital letter
        after the first one have none, unless they are in names."""
        cdef Py_UCS4 c
        result = self.cache.get(word)
        if result is not None:
            return <tuple>result
        if word in self.names:
            result = self.names[word]
        elif word.endswith("s") and word[: len(word) - 1] in self.names:
            result = self.names[word[: len(word) - 1]]
        elif any(c.isupper() for c in word[1:]):
            result = ()
        else:
            result = self.liang(word)
        self.cache[word] = result
        return <tuple>result

    cdef tuple liang(self, str word):
        """Positions of soft hyphens in a word, from the patterns."""
        cdef str pointed = "." + word.lower() + "."
        cdef Py_ssize_t m = len(pointed)
        cdef Py_ssize_t i, j, k, offset, stop
        cdef Py_ssize_t right = len(word) - self.right
        cdef list values = [0] * (m + 1)
        for i in range(m - 1):
            stop = min(i + self.maxlen, m) + 1
            for j in range(i + 1, stop):
                pattern = self.patterns.get(pointed[i:j])
                if pattern is None:
                    continue
                offset = pattern[0]
                for k, v in enumerate(pattern[1]):
                    if v > values[i + offset + k]:
                        values[i + offset + k] = v
        return tuple(
            i - 1
            for i in range(m + 1)
            if values[i] % 2 and self.left <= i - 1 <= right
        )


cdef list hyphen_positions(str text, list starts, list hyphenators):
    """Positions where soft hyphens go in the words of text, except in URLs.
    starts has the position of the first char of each slot and hyphenators the
    Hyphenator of each slot, or None."""
    cdef Py_ssize_t n = len(text)
    cdef Py_ssize_t slots = len(starts)
    cdef Py_ssize_t i = 0, j, start, word, owner = 0
    cdef Py_UCS4 c
    cdef bint url, letters
    cdef list result = []
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
            if c == u"/" or c == u"@" or (
                c == u"."
                and start < j < i - 1
                and is_word(text[j - 1])
                and is_word(text[j + 1])
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
            while owner + 1 < slots and <Py_ssize_t>starts[owner + 1] <= word:
                owner += 1
            hyphenator = hyphenators[owner]
            if hyphenator is None:
                continue
            for p in (<Hyphenator>hyphenator).positions(text[word:j]):
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
    "€", "$",
)


cdef inline bint is_figure(Py_UCS4 c):
    """Same as [0-9] in Python regular expressions."""
    return u"0" <= c <= u"9"


cdef bint boundary(str text, Py_ssize_t i):
    """Whether there is a word boundary (\\b) before text[i]."""
    cdef bint before = i > 0 and is_word(text[i - 1])
    cdef bint after = i < len(text) and is_word(text[i])
    return before != after


cdef bint figures_at(str text, Py_ssize_t i):
    """Whether text[i:] starts with figures, followed by the end or by a char
    that is not part of a word."""
    cdef Py_ssize_t j = i, n = len(text)
    while j < n and is_figure(text[j]):
        j += 1
    return j > i and (j == n or not is_word(text[j]))


cdef bint unit_at(str text, Py_ssize_t i):
    """Whether text[i:] starts with a unit, not followed by a word char."""
    cdef Py_ssize_t end, n = len(text)
    for unit in UNITS:
        if text.startswith(unit, i):
            end = i + len(<str>unit)
            if end == n or not is_word(text[end]):
                return True
    return False


cdef bint narrow_space(str text, Py_ssize_t i):
    """Whether the space at i becomes a narrow no-break space."""
    cdef Py_ssize_t j, start, n = len(text)
    cdef Py_UCS4 c = text[i]
    # Before some punctuation marks
    if i + 1 < n and text[i + 1] in u":;!?%»":
        return True
    # After an opening guillemet
    if i > 0 and text[i - 1] == u"«":
        return True
    if figures_at(text, i + 1):
        # Between figures, like "1 000"
        if i > 0 and is_figure(text[i - 1]):
            return True
        # Version numbers, like "Python 3"
        start = i
        while start > 0 and is_word(text[start - 1]):
            start -= 1
        if i - start >= 2 and u"A" <= text[start] <= u"Z":
            for j in range(start + 1, i):
                if not (u"a" <= text[j] <= u"z" or u"A" <= text[j] <= u"Z"):
                    break
            else:
                return True
    # Known units, like "10 km"
    if c == u" " or c == NBSP:
        start = i
        while start > 0 and is_figure(text[start - 1]):
            start -= 1
        if start < i and boundary(text, start) and unit_at(text, i + 1):
            return True
    # Other units, already with a no-break space in the source
    if c == NBSP and i + 1 < n and is_word(text[i + 1]):
        start = i
        while start > 0 and (is_figure(text[start - 1]) or text[start - 1] in u",."):
            start -= 1
        for j in range(start, i):
            if boundary(text, j):
                return True
    return False


cdef class Run:
    """Text of several slots as one string, so patterns work across inline
    elements. OBJECT stands for an element whose text is not part of the run.
    write() puts the result back in the slots.

    The chars of a slot are next to each other. starts has the position of the
    first char of each slot. For <p>Say <em>"yes</em>" now</p>, the slots are
    p.text, em.text and em.tail:

        text    S a y ␣ " y e s " ␣ n o w
        starts  0       4       8

    """

    cdef public list slots
    cdef public list hyphenators  # for each slot, or None
    cdef public list starts
    cdef public str text

    def __init__(self):
        self.slots = []
        self.hyphenators = []
        self.starts = []
        self.text = ""

    def add(self, slot, Hyphenator hyphenator=None):
        """Add the text of a slot at the end. The hyphenator is used for this
        text. An empty slot is not added.

        In the example, the run is built with:

            run.add(Slot(p, "text"))
            run.add(Slot(em, "text"))
            run.add(Slot(em, "tail"))

        """
        cdef str text = slot.get()
        if not text:
            return
        self.starts.append(len(self.text))
        self.text += text
        self.slots.append(slot)
        self.hyphenators.append(hyphenator)

    def opaque(self):
        """Add an element whose text is kept as is, like <code>. It becomes one
        OBJECT char, inside the slot before it. write() drops it. Patterns see
        it as a word but cannot change it.

            <p>Run <code>ls</code>.</p>

            text    R u n ␣ OBJECT .
            starts  0              5

        """
        self.text += OBJECT

    def edit(self, list changes):
        """Replace spans of the text, in order and without overlap. The new text
        goes to the slot of the first replaced char. An insertion goes to the
        slot of the char before it, unless this char is OBJECT. Spans with
        OBJECT are not changed.

        In the example, (3, 4, "_") and (8, 8, "!") give:

            text    S a y _ " y e s ! " ␣ n o w
            starts  0       4         9

        """
        cdef str text = self.text
        cdef list old = self.starts
        cdef list pieces = []
        cdef list starts = []
        cdef Py_ssize_t last = 0, k = 0, n = len(old), length = 0
        cdef Py_ssize_t start, end, first
        cdef str value
        for start, end, value in changes:
            first = start if start < end else start - 1
            if OBJECT in text[first:end]:
                continue
            pieces.append(text[last:start])
            # length is now the new position of start
            length += start - last
            # Slots starting up to the first char keep their place, the
            # next ones up to the end of the span start after the new text
            while k < n and <Py_ssize_t>old[k] <= first:
                starts.append(<Py_ssize_t>old[k] + length - start)
                k += 1
            pieces.append(value)
            length += len(value)
            while k < n and <Py_ssize_t>old[k] <= end:
                starts.append(length)
                k += 1
            last = end
        if not pieces:
            return
        pieces.append(text[last:])
        while k < n:
            starts.append(<Py_ssize_t>old[k] + length - last)
            k += 1
        self.text = "".join(pieces)
        self.starts = starts

    def smarten(self):
        """Quotes and ellipses."""
        cdef str text = self.text
        cdef Py_ssize_t i, n = len(text)
        cdef Py_UCS4 c, before
        cdef list changes
        if u"'" in text or u'"' in text:
            # '80s
            changes = []
            for i in range(n - 3):
                if (
                    text[i] == u"'"
                    and (i == 0 or text[i - 1].isspace())
                    and text[i + 1].isdecimal()
                    and text[i + 2].isdecimal()
                    and text[i + 3] == u"s"
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
                if c != u"'" and c != u'"':
                    continue
                if i + 1 < n and text[i + 1].isspace():
                    continue
                if i > 0:
                    before = text[i - 1]
                    if not (
                        before.isspace()
                        or before in u"([{“‘«"
                        or (before in u"—–" and i + 1 < n and is_word(text[i + 1]))
                    ):
                        continue
                changes.append((i, i + 1, "‘" if c == u"'" else "“"))
            self.edit(changes)
            # Other quotes are closing
            text = self.text
            changes = []
            for i in range(n):
                c = text[i]
                if c == u"'" or c == u'"':
                    changes.append((i, i + 1, "’" if c == u"'" else "”"))
            self.edit(changes)
        text = self.text
        if u"..." in text:
            changes = []
            i = 0
            n = len(text)
            while i + 3 <= n:
                if text[i] == u"." and text[i + 1] == u"." and text[i + 2] == u".":
                    changes.append((i, i + 3, "…"))
                    i += 3
                else:
                    i += 1
            self.edit(changes)

    def space(self):
        """French punctuation and figures. Some spaces become narrow no-break
        spaces. A rule only turns a space into a narrow no-break space. This
        cannot create or remove a match for another rule, so all rules look at
        the same text.

        """
        cdef str text = self.text
        cdef Py_ssize_t i
        cdef list changes = []
        for i in range(len(text)):
            if text[i].isspace() and narrow_space(text, i):
                changes.append((i, i + 1, NNBSP))
        self.edit(changes)

    def hyphenate(self):
        """Add soft hyphens in words of slots with a hyphenator, except in
        URLs.

        """
        if all(h is None for h in self.hyphenators):
            return
        self.edit([
            (p, p, SHY)
            for p in hyphen_positions(self.text, self.starts, self.hyphenators)
        ])

    def write(self):
        """Put the text back in the slots, using starts. OBJECT chars are
        dropped. Only slots with a different text are changed. A slot left empty
        becomes None. In the example:

            p.text   "Say "
            em.text  "“yes"
            em.tail  "” now"

        """
        cdef Py_ssize_t k, n = len(self.slots)
        cdef Py_ssize_t start, end
        cdef str text
        for k in range(n):
            start = self.starts[k]
            end = self.starts[k + 1] if k + 1 < n else len(self.text)
            text = self.text[start:end].replace(OBJECT, "")
            slot = self.slots[k]
            if text != slot.get():
                slot.put(text or None)


cdef bint joined(Py_UCS4 c, Py_UCS4 before):
    """Whether c belongs to the grapheme cluster of the char before it. This
    is an approximation: marks, format chars, skin tones and chars after a
    ZWJ."""
    if before == ZWJ:
        return True
    if c < u"\x80":
        return False
    if u"\U0001f3fb" <= c <= u"\U0001f3ff":
        return True
    return unicodedata.category(c) in ("Mn", "Mc", "Me", "Cf")


def last_line(list texts):
    """Remove line break opportunities at the end of a block, so the last line
    has at least LAST_LINE grapheme clusters. Spaces become no-break spaces.
    Soft hyphens and zero-width spaces are removed. texts has the text of each
    slot of the block. Return the new text of each slot.

    """
    cdef list chars = list("".join(texts))
    cdef list spaces = []
    cdef Py_ssize_t count = 0, j, start = 0
    cdef Py_UCS4 c, before
    for j in range(len(chars) - 1, -1, -1):
        if count >= LAST_LINE:
            break
        c = chars[j]
        if c == SHY or c == ZWSP:
            chars[j] = ""
        elif c in u" \t\n\x0c\r":
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

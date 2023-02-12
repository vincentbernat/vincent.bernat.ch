# -*- coding: utf-8 -*-
"""Extract glyphs used in code and regular blocks."""

import sys
import unicodedata
import functools
import markdown
from markdown.extensions import codehilite

glyphs = {
    "monospace": set(
        [
            "\u202f",  # NARROW NO-BREAK SPACE
            "û",  # SMALL LETTER U WITH CIRCUMFLEX (for août)
        ]
    ),
    "regular": set(
        [
            "\u2026",  # HORIZONTAL ELLIPSIS
            "\u2019",  # RIGHT SINGLE QUOTATION MARK
            "\u200b",  # ZERO WIDTH SPACE
            "\ufeff",  # ZERO WIDTH NO-BREAK SPACE
        ]
    ),
}

for c in range(sys.maxunicode + 1):
    u = chr(c)
    if unicodedata.category(u) == "Zs":
        glyphs["regular"].add(u)


class GlyphsTreeProcessor(markdown.treeprocessors.Treeprocessor):
    def __init__(self, glyphs, output):
        self.output = output
        self.glyphs = glyphs

    def run(self, root):
        for glyphs in self.extract(root):
            if glyphs is None:
                continue
            self.glyphs |= set(glyphs)
        with open(self.output, "wb") as f:
            f.write(
                "".join(sorted(g for g in self.glyphs if ord(g) >= 0x20)).encode(
                    "utf-8"
                )
            )


class MonospaceGlyphsTreeprocessor(GlyphsTreeProcessor):
    def extract(self, root):
        for code in root.findall(".//code"):
            yield code.text


class RegularGlyphsTreeprocessor(GlyphsTreeProcessor):
    def extract(self, root):
        for element in root.iter():
            if element.tag == "code":
                continue
            yield element.text
            yield element.tail


class GlyphsExtension(markdown.Extension):
    def extendMarkdown(self, md, md_globals):
        md.registerExtension(self)
        patch()

        # Regular glyphs (as late as possible)
        md.treeprocessors.add(
            "regularglyphs",
            RegularGlyphsTreeprocessor(glyphs["regular"], "glyphs-regular.txt"),
            "_end",
        )
        # Inline code (after inline, only inline code is embedded in code)
        md.treeprocessors.add(
            "monospaceglyphs2",
            MonospaceGlyphsTreeprocessor(glyphs["monospace"], "glyphs-monospace.txt"),
            ">inline",
        )


def makeExtension(configs=None):
    return GlyphsExtension(configs)


@functools.cache
def patch():
    previous = codehilite.highlight

    def new(src, lexer, formatter):
        glyphs["monospace"] |= set(src)
        return previous(src, lexer, formatter)

    codehilite.highlight = new

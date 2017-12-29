# -*- coding: utf-8 -*-
"""Extract glyphs used in code and regular blocks."""

import sys
import markdown
import unicodedata

glyphs = {
    'monospace': set(),
    'regular': set([
        u"\u2019",              # RIGHT SINGLE QUOTATION MARK
        u"\u200b",              # ZERO WIDTH SPACE
        u"\ufeff",              # ZERO WIDTH NO-BREAK SPACE
    ])
}

for c in xrange(sys.maxunicode+1):
    u = unichr(c)
    if unicodedata.category(u) == 'Zs':
        glyphs['regular'].add(u)


class GlyphsTreeProcessor(markdown.treeprocessors.Treeprocessor):
    def __init__(self, glyphs, output):
        self.output = output
        self.glyphs = glyphs

    def run(self, root):
        for glyphs in self.extract(root):
            if glyphs is None:
                continue
            self.glyphs |= set(glyph
                               for glyph in glyphs
                               if ord(glyph) >= 0x20)
        with open(self.output, "w") as f:
            f.write("".join(sorted(self.glyphs)).encode('utf-8'))


class MonospaceGlyphsTreeprocessor(GlyphsTreeProcessor):
    def extract(self, root):
        for code in root.findall('.//code'):
            yield code.text


class RegularGlyphsTreeprocessor(GlyphsTreeProcessor):
    def extract(self, root):
        for element in root.iter():
            if element.tag == 'code':
                continue
            yield element.text
            yield element.tail


class GlyphsExtension(markdown.Extension):
    def extendMarkdown(self, md, md_globals):
        # Regular glyphs (as late as possible)
        md.treeprocessors.add('regularglyphs',
                              RegularGlyphsTreeprocessor(
                                  glyphs['regular'],
                                  'glyphs-regular.txt'),
                              '_end')
        # Code blocks (before hilite, only code blocks are embedded in code)
        md.treeprocessors.add('monospaceglyphs1',
                              MonospaceGlyphsTreeprocessor(
                                  glyphs['monospace'],
                                  'glyphs-monospace.txt'),
                              '<hilite')
        # Inline code (after inline, only inline code is embedded in code)
        md.treeprocessors.add('monospaceglyphs2',
                              MonospaceGlyphsTreeprocessor(
                                  glyphs['monospace'],
                                  'glyphs-monospace.txt'),
                              '>inline')


def makeExtension(configs=None):
    return GlyphsExtension(configs)

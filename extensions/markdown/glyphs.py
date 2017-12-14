# -*- coding: utf-8 -*-
"""Extract glyphs used in code and regular blocks."""

import markdown

glyphs = {
    'monospace': set(),
    'regular': set()
}


class MonospaceGlyphsTreeprocessor(markdown.treeprocessors.Treeprocessor):
    def __init__(self, glyphs, output):
        self.output = output
        self.glyphs = glyphs

    def run(self, root):
        for code in root.findall('.//code'):
            if code.text is None:
                continue
            self.glyphs |= set(code.text)
        with open(self.output, "w") as f:
            f.write("".join(self.glyphs).encode('utf-8'))


class RegularGlyphsTreeprocessor(markdown.treeprocessors.Treeprocessor):
    def __init__(self, glyphs, output):
        self.output = output
        self.glyphs = glyphs

    def run(self, root):
        for element in root.iter():
            if element.tag == 'code':
                continue
            if element.text is not None:
                self.glyphs |= set(element.text)
            if element.tail is not None:
                self.glyphs |= set(element.tail)
        with open(self.output, "w") as f:
            f.write("".join(self.glyphs).encode('utf-8'))


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

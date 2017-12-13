# -*- coding: utf-8 -*-
"""Extract glyphs used in code blocks."""

import markdown

glyphs = set()


class CodeglyphsTreeprocessor(markdown.treeprocessors.Treeprocessor):
    def __init__(self, glyphs, output):
        self.output = output
        self.glyphs = glyphs

    def run(self, root):
        for code in root.findall('.//code'):
            self.glyphs |= set(code.text)
        with open(self.output, "w") as f:
            f.write("".join(self.glyphs).encode('utf-8'))


class CodeglyphsExtension(markdown.Extension):
    def extendMarkdown(self, md, md_globals):
        # Needs to come before escape matching because \ is pretty
        # important in LaTeX
        md.treeprocessors.add('codeglyphs',
                              CodeglyphsTreeprocessor(glyphs, 'glyphs.txt'),
                              '_begin')


def makeExtension(configs=None):
    return CodeglyphsExtension(configs)

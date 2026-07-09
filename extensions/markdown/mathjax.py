"""Skip any processing for · ... · or ·· ... ··.

This will be processed later by MathJax.

"""

import markdown
import xml.etree.ElementTree as etree


class MathJaxPattern(markdown.inlinepatterns.InlineProcessor):
    def __init__(self, md):
        super().__init__(r"(?<!\\)(··?)(.+?)\1", md)

    def handleMatch(self, m, data):
        node = etree.Element("x-latex")
        node.text = markdown.util.AtomicString(m.group(1) + m.group(2) + m.group(1))
        return node, m.start(0), m.end(0)


class MathJaxExtension(markdown.Extension):
    def extendMarkdown(self, md):
        # Needs to come before escape matching because \ is pretty
        # important in LaTeX
        md.inlinePatterns.register(MathJaxPattern(md), "mathjax", 185)


def makeExtension(**kwargs):
    return MathJaxExtension(**kwargs)

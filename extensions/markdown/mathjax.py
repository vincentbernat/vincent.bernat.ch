# -*- encoding: utf-8 -*-
# Skip any processing for · ... · or ·· ... ··
# This will be processed later by MathJax

import markdown
from markdown.util import etree

class MathJaxPattern(markdown.inlinepatterns.Pattern):

    def __init__(self):
        markdown.inlinepatterns.Pattern.__init__(self, ur'(?<!\\)(··?)(.+?)\2')

    def handleMatch(self, m):
        node = etree.Element("latex")
        node.text = markdown.util.AtomicString(m.group(2) + m.group(3) + m.group(2))
        return node

class MathJaxExtension(markdown.Extension):
    def extendMarkdown(self, md, md_globals):
        # Needs to come before escape matching because \ is pretty important in LaTeX
        md.inlinePatterns.add('mathjax', MathJaxPattern(), '<escape')

def makeExtension(configs=None):
    return MathJaxExtension(configs)

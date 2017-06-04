# -*- coding: utf-8 -*-
"""Turn tables into responsive tables.

This is just a matter of wrapping them into a container.

"""

from markdown import Extension
from markdown.treeprocessors import Treeprocessor
from markdown.util import etree


class ResponsiveTableExtension(Extension):

    def extendMarkdown(self, md, md_globals):
        md.registerExtension(self)
        self.processor = ResponsiveTableTreeprocessor()
        self.processor.md = md
        self.processor.config = self.getConfigs()
        md.treeprocessors.add('headerid', self.processor, '_end')


class ResponsiveTableTreeprocessor(Treeprocessor):

    def run(self, node):
        for idx, child in enumerate(node):
            if child.tag == 'table':
                outer = etree.Element("div")
                outer.set("class", "lf-table")
                outer.insert(0, child)
                node.remove(child)
                node.insert(idx, outer)


def makeExtension(**kwargs):
    return ResponsiveTableExtension(**kwargs)

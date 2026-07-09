"""Turn tables into responsive tables.

This is just a matter of wrapping them into a container. This enables us to
scroll them (while keeping display: table) and center them (while keeping them
overflow in margins if needed).
"""

from markdown import Extension
from markdown.treeprocessors import Treeprocessor
import xml.etree.ElementTree as etree


class ResponsiveTableExtension(Extension):
    def extendMarkdown(self, md):
        md.registerExtension(self)
        self.processor = ResponsiveTableTreeprocessor(md)
        self.processor.config = self.getConfigs()
        md.treeprocessors.register(self.processor, "responsive-table", -10)


class ResponsiveTableTreeprocessor(Treeprocessor):
    def run(self, node):
        for idx, child in enumerate(node):
            if child.tag == "table":
                outer = etree.Element("div")
                outer.set("class", "lf-table")
                outer.insert(0, child)
                node.remove(child)
                node.insert(idx, outer)


def makeExtension(**kwargs):
    return ResponsiveTableExtension(**kwargs)

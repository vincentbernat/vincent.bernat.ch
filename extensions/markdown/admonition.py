from markdown.extensions import Extension
from markdown.blockprocessors import BlockProcessor
from markdown.treeprocessors import Treeprocessor
import xml.etree.ElementTree as etree
import re


class AdmonitionExtension(Extension):
    def extendMarkdown(self, md):
        md.registerExtension(self)
        md.parser.blockprocessors.register(
            AdmonitionProcessor(md.parser), "shortadmonition", 105
        )
        # Runs after attr_list (priority 8)
        md.treeprocessors.register(
            AdmonitionClassProcessor(md), "shortadmonition", 7
        )


class AdmonitionProcessor(BlockProcessor):
    RE = re.compile(r'(?:^|\n)!!! +"(.*?)" +')

    def test(self, parent, block):
        return self.RE.search(block)

    def run(self, parent, blocks):
        block = blocks.pop(0)
        m = self.RE.search(block)

        if m:
            block = block[m.end() :]  # removes the first line

        if m:
            div = etree.SubElement(parent, "div")
            div.set("class", "admonition")
            title = m.group(1)
            p = etree.SubElement(div, "p")
            p.text = title
            p.set("class", "admonition-title")

        self.parser.parseChunk(div, block)


class AdmonitionClassProcessor(Treeprocessor):
    """Move the classes of the last paragraph of an admonition to the
    admonition itself. This way, an attribute list at the end of an admonition
    applies to the whole block."""

    def run(self, doc):
        for div in doc.iter("div"):
            classes = div.get("class", "").split()
            if "admonition" not in classes or not len(div):
                continue
            last = div[-1]
            if last.tag != "p" or "admonition-title" in last.get("class", "").split():
                continue
            moved = last.get("class")
            if not moved:
                continue
            del last.attrib["class"]
            div.set("class", " ".join(classes + moved.split()))


def makeExtension(*args, **kwargs):
    return AdmonitionExtension(*args, **kwargs)

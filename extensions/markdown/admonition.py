from markdown.extensions import Extension
from markdown.blockprocessors import BlockProcessor
from markdown.util import etree
import re


class AdmonitionExtension(Extension):
    def extendMarkdown(self, md, md_globals):
        md.registerExtension(self)
        md.parser.blockprocessors.add(
            "shortadmonition", AdmonitionProcessor(md.parser), "_begin"
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


def makeExtension(*args, **kwargs):
    return AdmonitionExtension(*args, **kwargs)

import re
import xml.etree.ElementTree as etree
from typing import Any
from xml.etree.ElementTree import Element

from markdown.blockprocessors import BlockProcessor
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor


class AdmonitionExtension(Extension):
    def extendMarkdown(self, md: Any) -> None:
        md.registerExtension(self)
        md.parser.blockprocessors.register(
            AdmonitionProcessor(md.parser), "shortadmonition", 105
        )
        # Runs after attr_list (priority 8)
        md.treeprocessors.register(AdmonitionClassProcessor(md), "shortadmonition", 7)


class AdmonitionProcessor(BlockProcessor):
    RE = re.compile(r'(?:^|\n)!!! +"(.*?)" +')

    def test(self, parent: Element, block: str) -> bool:
        return self.RE.search(block) is not None

    def run(self, parent: Element, blocks: list[str]) -> bool:
        m = self.RE.search(blocks[0])
        if m is None:
            return False
        block = blocks.pop(0)
        if m.start() > 0:
            self.parser.parseBlocks(parent, [block[: m.start()]])
        div = etree.SubElement(parent, "div")
        div.set("class", "admonition")
        p = etree.SubElement(div, "p")
        p.text = m.group(1)
        p.set("class", "admonition-title")
        self.parser.parseChunk(div, block[m.end() :])
        return True


class AdmonitionClassProcessor(Treeprocessor):
    """Move the classes of the last paragraph of an admonition to the
    admonition itself. This way, an attribute list at the end of an admonition
    applies to the whole block."""

    def run(self, doc: Element) -> None:
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


def makeExtension(*args: Any, **kwargs: Any) -> AdmonitionExtension:
    return AdmonitionExtension(*args, **kwargs)

import re
from typing import Any
from xml.etree.ElementTree import Element

from markdown.extensions import Extension
from markdown.extensions.admonition import AdmonitionProcessor as BaseProcessor
from markdown.treeprocessors import Treeprocessor


class AdmonitionExtension(Extension):
    def extendMarkdown(self, md: Any) -> None:
        md.registerExtension(self)
        md.parser.blockprocessors.register(
            AdmonitionProcessor(md.parser), "shortadmonition", 105
        )
        # Runs after attr_list (priority 8)
        md.treeprocessors.register(AdmonitionClassProcessor(md), "shortadmonition", 7)


class AdmonitionProcessor(BaseProcessor):
    """Same as the builtin admonition, but with a title and without a type."""

    RE = re.compile(r'(?:^|\n)!!! +"(.*?)" *(?:\n|$)')

    def get_class_and_title(self, match: re.Match[str]) -> tuple[str, str | None]:
        return "", match.group(1) or None


class AdmonitionClassProcessor(Treeprocessor):
    """Move the classes of the first paragraph of an admonition to the
    admonition itself. This way, an attribute list at the end of this paragraph
    applies to the whole block.

    """

    def run(self, doc: Element) -> None:
        for div in doc.iter("div"):
            classes = div.get("class", "").split()
            if "admonition" not in classes:
                continue
            children = [
                child
                for child in div
                if "admonition-title" not in child.get("class", "").split()
            ]
            first = children[0] if children else None
            if first is not None and first.tag == "p" and first.get("class"):
                classes += first.attrib.pop("class").split()
            div.set("class", " ".join(classes))


def makeExtension(*args: Any, **kwargs: Any) -> AdmonitionExtension:
    return AdmonitionExtension(*args, **kwargs)

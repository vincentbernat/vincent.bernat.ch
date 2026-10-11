"""Extract glyphs used in code and regular blocks."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, Any
from xml.etree.ElementTree import Element

import markdown
from markdown.extensions import codehilite
from pygments.formatters.html import HtmlFormatter

from . import collect

if TYPE_CHECKING:
    from _typeshed import SupportsWrite


class GlyphsTreeProcessor(markdown.treeprocessors.Treeprocessor):
    def __init__(self, kind: str) -> None:
        self.kind = kind

    def extract(self, root: Element) -> Iterator[str | None]:
        raise NotImplementedError

    def run(self, root: Element) -> None:
        for glyphs in self.extract(root):
            if glyphs is None:
                continue
            collect(self.kind, glyphs)


class MonospaceGlyphsTreeprocessor(GlyphsTreeProcessor):
    def extract(self, root: Element) -> Iterator[str | None]:
        for code in root.findall(".//code"):
            yield code.text


class RegularGlyphsTreeprocessor(GlyphsTreeProcessor):
    def extract(self, root: Element) -> Iterator[str | None]:
        for element in root.iter():
            if element.tag == "code":
                continue
            yield element.text
            yield element.tail


class MonospaceGlyphsFormatter(HtmlFormatter):
    """Grab glyphs from highlighted code."""

    def format(
        self, tokensource: Iterable[tuple[Any, str]], outfile: SupportsWrite[str]
    ) -> None:
        tokensource = list(tokensource)
        collect("monospace", "".join(value for _, value in tokensource))
        return super().format(tokensource, outfile)


class GlyphsExtension(markdown.Extension):
    def extendMarkdown(self, md: Any) -> None:
        md.registerExtension(self)

        # Highlighted code is turned into raw HTML before the tree processors
        # run, so glyphs are collected from a custom formatter. The tree
        # processor copies the configuration when registered, while fenced_code
        # reads it on first use: both need the formatter.
        for extension in md.registeredExtensions:
            if isinstance(extension, codehilite.CodeHiliteExtension):
                extension.setConfig("pygments_formatter", MonospaceGlyphsFormatter)
        if "hilite" in md.treeprocessors:
            md.treeprocessors["hilite"].config[
                "pygments_formatter"
            ] = MonospaceGlyphsFormatter

        # Regular glyphs (as late as possible)
        md.treeprocessors.register(
            RegularGlyphsTreeprocessor("regular"), "regularglyphs", -5
        )
        # Inline code (after inline, only inline code is embedded in code)
        md.treeprocessors.register(
            MonospaceGlyphsTreeprocessor("monospace"), "monospaceglyphs", 15
        )


def makeExtension(**kwargs: Any) -> GlyphsExtension:
    return GlyphsExtension(**kwargs)

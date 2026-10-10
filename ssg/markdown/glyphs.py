"""Extract glyphs used in code and regular blocks."""

import markdown
from markdown.extensions import codehilite
from pygments.formatters.html import HtmlFormatter

from . import collect


class GlyphsTreeProcessor(markdown.treeprocessors.Treeprocessor):
    def __init__(self, kind):
        self.kind = kind

    def run(self, root):
        for glyphs in self.extract(root):
            if glyphs is None:
                continue
            collect(self.kind, glyphs)


class MonospaceGlyphsTreeprocessor(GlyphsTreeProcessor):
    def extract(self, root):
        for code in root.findall(".//code"):
            yield code.text


class RegularGlyphsTreeprocessor(GlyphsTreeProcessor):
    def extract(self, root):
        for element in root.iter():
            if element.tag == "code":
                continue
            yield element.text
            yield element.tail


class MonospaceGlyphsFormatter(HtmlFormatter):
    """Grab glyphs from highlighted code."""

    def format(self, tokensource, outfile):
        tokensource = list(tokensource)
        collect("monospace", "".join(value for _, value in tokensource))
        return super().format(tokensource, outfile)


class GlyphsExtension(markdown.Extension):
    def extendMarkdown(self, md):
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


def makeExtension(**kwargs):
    return GlyphsExtension(**kwargs)

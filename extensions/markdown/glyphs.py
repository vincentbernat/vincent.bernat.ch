"""Extract glyphs used in code and regular blocks."""

import sys
import unicodedata
import markdown
from hyde.plugin import Plugin
from markdown.extensions import codehilite
from pygments.formatters.html import HtmlFormatter

glyphs = {
    "monospace": {
        "\u00fb",  # SMALL LETTER U WITH CIRCUMFLEX (for août)
    },
    "regular": {
        "\u2026",  # HORIZONTAL ELLIPSIS
        "\u2019",  # RIGHT SINGLE QUOTATION MARK
    },
}
outputs = {
    "monospace": ".glyphs-monospace.txt",
    "regular": ".glyphs-regular.txt",
}

for c in range(sys.maxunicode + 1):
    u = chr(c)
    # Zs is Space Separator Category (it contains all non-zero-width spaces)
    # Cf is Format Category (it contains zero-width-spaces)
    if unicodedata.category(u) in ("Zs", "Cf"):
        for kind in glyphs:
            glyphs[kind].add(u)


class GlyphsTreeProcessor(markdown.treeprocessors.Treeprocessor):
    def __init__(self, glyphs):
        self.glyphs = glyphs

    def run(self, root):
        for glyphs in self.extract(root):
            if glyphs is None:
                continue
            self.glyphs |= set(glyphs)


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
        glyphs["monospace"] |= {g for _, value in tokensource for g in value}
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
            RegularGlyphsTreeprocessor(glyphs["regular"]),
            "regularglyphs",
            -5,
        )
        # Inline code (after inline, only inline code is embedded in code)
        md.treeprocessors.register(
            MonospaceGlyphsTreeprocessor(glyphs["monospace"]),
            "monospaceglyphs",
            15,
        )


class GlyphsPlugin(Plugin):
    """Write the glyphs used by the site once generated."""

    def site_complete(self):
        for kind, output in outputs.items():
            wanted = sorted(g for g in glyphs[kind] if ord(g) >= 0x20)
            with open(output, "w", encoding="utf-8") as f:
                f.write("".join(wanted))


def makeExtension(**kwargs):
    return GlyphsExtension(**kwargs)

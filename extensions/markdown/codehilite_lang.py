# -*- coding: utf-8 -*-
"""Add language to highlighted code.

"""

from pygments import highlight as pygments_highlight
from pygments.formatters.html import HtmlFormatter
from pyquery import PyQuery as pq
from markdown import Extension
from markdown.extensions import codehilite
from .glyphs import glyphs


class CodeHiliteLangExtension(Extension):
    def extendMarkdown(self, md, md_globals):
        md.registerExtension(self)

        def new_codehilite_highlight(src, lexer, formatter):
            # Not pretty, but that's easier to do that here. This works because
            # highlighting happens before inlining.
            glyphs["monospace"] |= set(glyph for glyph in src if ord(glyph) >= 0x20)
            lang = lexer.name.lower().replace(" ", "-")
            result = pygments_highlight(src, lexer, formatter)
            if isinstance(formatter, HtmlFormatter):
                d = pq(result, parser="html")
                d.add_class("language-{}".format(lang))
                result = d.outer_html()
            return result

        codehilite.highlight = new_codehilite_highlight


def makeExtension(**kwargs):
    return CodeHiliteLangExtension(**kwargs)

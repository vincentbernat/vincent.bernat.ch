# -*- coding: utf-8 -*-
"""Add language to highlighted code.

"""

from pygments.formatters.html import HtmlFormatter
from pyquery import PyQuery as pq
from markdown import Extension
from markdown.extensions import codehilite


class CodeHiliteLangExtension(Extension):
    def extendMarkdown(self, md, md_globals):
        md.registerExtension(self)

        previous = codehilite.highlight

        def new(src, lexer, formatter):
            lang = lexer.name.lower().replace(" ", "-")
            result = previous(src, lexer, formatter)
            if isinstance(formatter, HtmlFormatter):
                d = pq(result, parser="html")
                d.add_class("language-{}".format(lang))
                result = d.outer_html()
            return result

        codehilite.highlight = new


def makeExtension(**kwargs):
    return CodeHiliteLangExtension(**kwargs)

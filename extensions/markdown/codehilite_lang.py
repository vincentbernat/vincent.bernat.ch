# -*- coding: utf-8 -*-
"""Add language to highlighted code.

"""

import functools
from pygments.formatters.html import HtmlFormatter
from markdown import Extension
from markdown.extensions import codehilite


class CodeHiliteLangExtension(Extension):
    def extendMarkdown(self, md, md_globals):
        md.registerExtension(self)
        patch()


def makeExtension(**kwargs):
    return CodeHiliteLangExtension(**kwargs)


@functools.cache
def patch():
    previous = codehilite.highlight

    def new(src, lexer, formatter):
        lang = lexer.name.lower().replace(" ", "-")
        result = previous(src, lexer, formatter)
        if isinstance(formatter, HtmlFormatter):
            result = result.replace('class="', 'class="language-{} '.format(lang), 1)
        return result

    codehilite.highlight = new

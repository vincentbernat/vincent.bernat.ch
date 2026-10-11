"""Add language to highlighted code."""

import functools
from typing import Any

from markdown import Extension
from markdown.extensions import codehilite
from pygments.formatters.html import HtmlFormatter


class CodeHiliteLangExtension(Extension):
    def extendMarkdown(self, md: Any) -> None:
        md.registerExtension(self)
        patch()


def makeExtension(**kwargs: Any) -> CodeHiliteLangExtension:
    return CodeHiliteLangExtension(**kwargs)


@functools.cache
def patch() -> None:
    # The stubs do not know codehilite imports highlight() from Pygments
    previous = codehilite.highlight  # type: ignore[attr-defined]

    def new(src: str, lexer: Any, formatter: Any) -> str:
        lang = lexer.name.lower().replace(" ", "-")
        result = previous(src, lexer, formatter)
        if isinstance(formatter, HtmlFormatter):
            result = result.replace('class="', f'class="language-{lang} ', 1)
        return result

    codehilite.highlight = new  # type: ignore[attr-defined]

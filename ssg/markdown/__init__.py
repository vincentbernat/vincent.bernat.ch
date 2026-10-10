"""Markdown conversion."""

import sys
import unicodedata

from markdown import Markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.extra import ExtraExtension
from markdown.extensions.toc import TocExtension

# Glyphs and unknown references found during conversions, when not None
collected = None

# Glyphs always kept in fonts
BASE_GLYPHS = {
    "monospace": {
        "û",  # SMALL LETTER U WITH CIRCUMFLEX (for août)
    },
    "regular": {
        "…",  # HORIZONTAL ELLIPSIS
        "’",  # RIGHT SINGLE QUOTATION MARK
    },
}
for c in range(sys.maxunicode + 1):
    # Zs is Space Separator Category (it contains all non-zero-width spaces)
    # Cf is Format Category (it contains zero-width-spaces)
    if unicodedata.category(chr(c)) in ("Zs", "Cf"):
        for chars in BASE_GLYPHS.values():
            chars.add(chr(c))


def collect(kind, values):
    if collected is None:
        return
    if kind == "references":
        collected[kind].add(values)
    else:
        collected[kind].update(values)


def convert(text, site, l10n=None):
    return Markdown(
        extensions=[
            CodeHiliteExtension(guess_lang=False),
            ExtraExtension(footnotes={"BACKLINK_TEXT": "&#x2766;"}),
            TocExtension(permalink="#"),
            admonition.makeExtension(),
            glyphs.makeExtension(),
            katex.makeExtension(),
            shortlinks.makeExtension(l10n=l10n),
            textlinks.makeExtension(site=site),
            html_comments.makeExtension(),
            responsive_table.makeExtension(),
            codehilite_lang.makeExtension(),
            no_shortcut_links.makeExtension(),
            references.makeExtension(),
        ],
        output_format="html",
    ).convert(text)


# Extensions use collect()
from . import (  # noqa: E402
    admonition,
    codehilite_lang,
    glyphs,
    html_comments,
    katex,
    no_shortcut_links,
    references,
    responsive_table,
    shortlinks,
    textlinks,
)

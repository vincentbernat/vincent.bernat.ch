"""Typography: smart quotes and French punctuation."""

import re

import smartypants
from markupsafe import Markup
from typogrify.filters import process_ignores

NNBSP = "&#x202f;"
TAG = r"</?\w+((\s+\w+(\s*=\s*(?:\".*?\"|'.*?'|[^'\">\s]+))?)+\s*|\s*)/?>"

closing_double_quote = re.compile(r"""^&#8220;([,:;!\?])""")
possessive_quote = re.compile(r"""^&#8216;(?=s\s|\W|$)""")
space_before_punct = re.compile(r"""(\s|&nbsp;)([:;!\?%»])""")
space_after_punct = re.compile(r"""([«])(\s|&nbsp;)""")
space_between_figures = re.compile(r"""([0-9]|^)(\s|&nbsp;)([0-9]+(?:\W|$))""")
version_number = re.compile(r"""(\b[A-Z][a-zA-Z]+)(\s|&nbsp;)([0-9]+(?:\W|$))""")
# Cheating, the no-break space is already here
si_unit = re.compile(r"""(\b[0-9,.]+)(\u00a0|&nbsp;)(\w|€)""")
intra_tag = re.compile(
    rf"(?P<prefix>({TAG})?)" rf"(?P<text>([^<]*))" rf"(?P<suffix>({TAG})?)"
)


def fix(match):
    prefix = match.group("prefix") or ""
    text = match.group("text")

    # Misc fixes
    text = closing_double_quote.sub(r"&#8221;\1", text)
    text = possessive_quote.sub("&#8217;", text)

    # French punctuation
    text = space_before_punct.sub(NNBSP + r"\2", text)
    text = space_after_punct.sub(r"\1" + NNBSP, text)
    text = space_between_figures.sub(r"\1" + NNBSP + r"\3", text)
    text = version_number.sub(r"\1" + NNBSP + r"\3", text)
    text = si_unit.sub(r"\1" + NNBSP + r"\3", text)
    suffix = match.group("suffix") or ""
    return prefix + text + suffix


def typogrify(text):
    """Apply typography fixes outside code and formulas."""
    output = []
    for part, process in process_ignores(text, ["x-latex"]):
        if process:
            part = intra_tag.sub(fix, smartypants.smartypants(part))
        output.append(part)
    return Markup("".join(output))

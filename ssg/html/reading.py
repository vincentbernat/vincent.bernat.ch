"""Reading time of articles."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from pyquery import PyQuery as pq

if TYPE_CHECKING:
    from pyquery import PyQuery

    from ..model.resource import Resource

WORDS_PER_MINUTE = 200
CODE_LINES_PER_MINUTE = 30


def fix(resource: Resource, d: PyQuery) -> None:
    """Add a paragraph in .lf-reading-time with the reading time of the article
    in .lf-text. It must run before other changes to the article."""
    targets = d(".lf-reading-time")
    texts = d(".lf-text")
    if not targets or not texts:
        return
    article = pq(copy.deepcopy(texts[0]))
    code_blocks = article.find("pre")
    code_lines = sum(
        sum(1 for line in el.text_content().splitlines() if line.strip())
        for el in code_blocks
    )
    code_blocks.remove()
    article.find(".footnote").remove()
    words = len(article.text().split())
    minutes = max(
        1, round(words / WORDS_PER_MINUTE + code_lines / CODE_LINES_PER_MINUTE)
    )
    l10n = resource.meta.l10n
    for div in targets:
        p = div.makeelement("p", {"title": l10n.words.format(words)})
        p.text = l10n.reading_time[1 if minutes > 1 else 0].format(minutes)
        # Indent like the div
        previous = div.getprevious()
        before = previous.tail if previous is not None else div.getparent().text
        indent = (before or "").rpartition("\n")[2]
        div.text = f"\n{indent}  "
        p.tail = f"\n{indent}"
        div.append(p)

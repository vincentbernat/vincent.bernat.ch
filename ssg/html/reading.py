"""Reading time of articles."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from .dom import remove, select, text

if TYPE_CHECKING:
    import lxml.etree

    from ..model.resource import Resource

WORDS_PER_MINUTE = 200
CODE_LINES_PER_MINUTE = 30


def fix(resource: Resource, root: lxml.etree._Element) -> None:
    """Add a paragraph in .lf-reading-time with the reading time of the article
    in .lf-text. It must run before other changes to the article."""
    targets = select(root, ".lf-reading-time")
    texts = select(root, ".lf-text")
    if not targets or not texts:
        return
    article = copy.deepcopy(texts[0])
    code_blocks = article.findall(".//pre")
    code_lines = sum(
        sum(1 for line in "".join(el.itertext()).splitlines() if line.strip())
        for el in code_blocks
    )
    for el in code_blocks + select(article, ".footnote"):
        remove(el)
    words = len(text(article).split())
    minutes = max(
        1, round(words / WORDS_PER_MINUTE + code_lines / CODE_LINES_PER_MINUTE)
    )
    l10n = resource.meta.l10n
    for div in targets:
        p = div.makeelement("p", {"title": l10n.words.format(words)})
        p.text = l10n.reading_time[1 if minutes > 1 else 0].format(minutes)
        # Indent like the div
        previous = div.getprevious()
        parent = div.getparent()
        assert parent is not None
        before = previous.tail if previous is not None else parent.text
        indent = (before or "").rpartition("\n")[2]
        div.text = f"\n{indent}  "
        p.tail = f"\n{indent}"
        div.append(p)

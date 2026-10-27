"""Number links and list their URLs at the end of the article, for print."""

from __future__ import annotations

import urllib.parse
from typing import TYPE_CHECKING

from .. import config
from .dom import select, set_flag, text

if TYPE_CHECKING:
    import lxml.etree

    from ..model.resource import Resource


def number(resource: Resource, root: lxml.etree._Element) -> None:
    """Add a mark after each link in .lf-text and a list of their URLs at
    the end. Both are only displayed when printing."""
    texts = select(root, ".lf-text")
    if not texts:
        return
    article = texts[0]
    base = config.BASE + resource.url
    urls: dict[str, int] = {}
    for a in select(article, "a[href]"):
        href = a.get("href", "")
        if href.startswith("#"):
            continue
        url = urllib.parse.urljoin(base, href)
        if not url.startswith(("https://", "http://")):
            continue
        label = text(a)
        if not label or label in (url, url.partition("://")[2]):
            continue
        n = urls.setdefault(url, len(urls) + 1)
        mark = a.makeelement("span", {"class": "lf-print-ref"})
        set_flag(mark, "hidden")
        mark.text = f"[{n}]"
        mark.tail = a.tail
        a.tail = None
        a.addnext(mark)
    if not urls:
        return
    ol = article.makeelement("ol", {"class": "lf-print-links"})
    set_flag(ol, "hidden")
    for url in urls:
        li = ol.makeelement("li", {})
        link = li.makeelement("a", {"href": url})
        link.text = url
        li.append(link)
        ol.append(li)
    article.append(ol)

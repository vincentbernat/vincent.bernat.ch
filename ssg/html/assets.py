"""Stylesheets and scripts loaded only when a page needs them."""

from __future__ import annotations

import posixpath
from typing import TYPE_CHECKING

from .. import config
from .dom import select

if TYPE_CHECKING:
    import lxml.etree

    from ..model.site import Site


def load(site: Site, root: lxml.etree._Element) -> None:
    """Load additional scripts and stylesheets."""
    css_anchor = select(root, f'link[href="{site.media_url("css/luffy.css")}"]')
    js_anchor = select(root, f'script[src="{site.media_url("js/luffy.js")}"]')
    css_tags: list[dict[str, str]] = []
    js_tags: list[dict[str, str]] = []
    for selector, files, lazy in config.LOAD:
        if not select(root, selector):
            continue
        for f in files:
            src = site.media_url(f)
            name = posixpath.basename(f)
            if f.endswith(".css"):
                if lazy:
                    css_tags.append(
                        {
                            "rel": "stylesheet",
                            "data-href": src,
                            "data-name": name,
                            "href": "data:text/css;base64,",
                        }
                    )
                else:
                    css_tags.append({"rel": "stylesheet", "href": src})
            elif lazy:
                js_tags.append({"data-src": src, "data-name": name, "type": "module"})
            else:
                js_tags.append({"src": src, "data-name": name, "type": "module"})
    insert_after(css_anchor, "link", css_tags)
    insert_after(js_anchor, "script", js_tags)


def insert_after(
    anchor: list[lxml.etree._Element], tag: str, attributes: list[dict[str, str]]
) -> None:
    """Insert elements right after the anchor element, keeping a 2-space
    indentation."""
    if not anchor or not attributes:
        return
    el = anchor[0]
    tail = el.tail
    el.tail = "\n  "
    for i, attrib in enumerate(reversed(attributes)):
        new = el.makeelement(tag, attrib)
        new.tail = tail if i == 0 else "\n  "
        el.addnext(new)

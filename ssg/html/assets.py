"""Stylesheets and scripts loaded only when a page needs them."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from lxml.html import fragment_fromstring

from .. import config

if TYPE_CHECKING:
    from ..model.site import Site


def load(site: Site, d: Any) -> None:
    """Load additional scripts and stylesheets."""
    css_anchor = d(f'link[href="{site.media_url("css/luffy.css")}"]')
    js_anchor = d(f'script[src="{site.media_url("js/luffy.js")}"]')
    css_tags = []
    js_tags = []
    for selector, files, lazy in config.LOAD:
        if not d(selector):
            continue
        for f in files:
            src = site.media_url(f)
            name = os.path.basename(f)
            if f.endswith(".css"):
                if lazy:
                    css_tags.append(
                        f'<link rel="stylesheet" data-href="{src}" '
                        f'data-name="{name}" href="data:text/css;base64,">'
                    )
                else:
                    css_tags.append(f'<link rel="stylesheet" href="{src}">')
            elif lazy:
                js_tags.append(
                    f'<script data-src="{src}" data-name="{name}" type="module"></script>'
                )
            else:
                js_tags.append(
                    f'<script src="{src}" data-name="{name}" type="module"></script>'
                )
    insert_after(css_anchor, css_tags)
    insert_after(js_anchor, js_tags)


def insert_after(anchor: Any, tags: list[str]) -> None:
    """Insert the tags right after the anchor element, keeping a 2-space
    indentation."""
    if not anchor or not tags:
        return
    el = anchor[0]
    tail = el.tail
    el.tail = "\n  "
    for i, tag in enumerate(reversed(tags)):
        new = fragment_fromstring(tag)
        new.tail = tail if i == 0 else "\n  "
        el.addnext(new)

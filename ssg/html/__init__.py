"""Transform rendered HTML pages and feeds."""

from __future__ import annotations

from typing import TYPE_CHECKING

import lxml.etree
from pyquery import PyQuery as pq

from . import assets, figures, hashing, sidenotes, toc

if TYPE_CHECKING:
    from ..model.resource import Resource
    from ..model.site import Site

ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "xhtml": "http://www.w3.org/1999/xhtml",
}


def page(site: Site, resource: Resource, text: str) -> str:
    """Transform an HTML page."""
    d = pq(text, parser="html")
    figures.fix(site, resource, d)
    if resource.meta.get("sidenotes", True) is not False:
        sidenotes.convert(d)
    toc.fix(resource, d)
    assets.load(site, d)
    if site.mode.production:
        hashing.rewrite(site, d[0])
    return "<!DOCTYPE html>\n" + d.outer_html()


def feed(site: Site, resource: Resource, text: str) -> str:
    """Transform an Atom feed."""
    root = lxml.etree.fromstring(text.encode("utf-8"))
    xhtml = ATOM_NS["xhtml"]
    for div in root.iterfind("atom:entry/atom:content/xhtml:div", ATOM_NS):
        # Selectors of pyquery ignore namespaces
        for el in div.iter("{*}*"):
            el.tag = lxml.etree.QName(el).localname
        figures.fix(site, resource, pq(div))
        for el in div.iter("*"):
            name = lxml.etree.QName(el)
            if name.namespace is None:
                el.tag = f"{{{xhtml}}}{name.localname}"
    if site.mode.production:
        hashing.rewrite(site, root)
    return lxml.etree.tostring(
        root.getroottree(), xml_declaration=True, encoding="UTF-8"
    ).decode("utf-8")

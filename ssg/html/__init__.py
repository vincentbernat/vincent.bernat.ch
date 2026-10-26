"""Transform rendered HTML pages and feeds."""

from __future__ import annotations

from typing import TYPE_CHECKING

import lxml.etree
import lxml.html

from . import assets, figures, fingerprint, links, reading, sidenotes, toc

if TYPE_CHECKING:
    from ..model.resource import Resource
    from ..model.site import Site

ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "xhtml": "http://www.w3.org/1999/xhtml",
}


def page(site: Site, resource: Resource, text: str) -> str:
    """Transform an HTML page."""
    root = lxml.html.fromstring(text)
    reading.fix(resource, root)
    figures.fix(site, resource, root)
    if resource.meta.get("sidenotes", True) is not False:
        sidenotes.convert(root)
    toc.fix(resource, root)
    assets.load(site, root)
    fingerprint.rewrite(site, root)
    links.number(resource, root)
    return "<!DOCTYPE html>\n" + lxml.html.tostring(root, encoding="unicode")


def feed(site: Site, resource: Resource, text: str) -> str:
    """Transform an Atom feed."""
    root = lxml.etree.fromstring(text.encode("utf-8"))
    for div in root.iterfind("atom:entry/atom:content/xhtml:div", ATOM_NS):
        figures.fix(site, resource, div)
    fingerprint.rewrite(site, root)
    return lxml.etree.tostring(
        root.getroottree(), xml_declaration=True, encoding="UTF-8"
    ).decode("utf-8")

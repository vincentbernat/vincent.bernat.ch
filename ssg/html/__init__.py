"""Transform rendered HTML pages and feeds."""

import lxml.etree
from pyquery import PyQuery as pq

from . import assets, figures, hashing, sidenotes, toc

ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "xhtml": "http://www.w3.org/1999/xhtml",
}


def page(site, resource, text):
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


def feed(site, resource, text):
    """Transform an Atom feed."""
    root = lxml.etree.fromstring(text.encode("utf-8"))
    for c in root.findall("atom:entry/atom:content", ATOM_NS):
        div = c.find("xhtml:div", ATOM_NS)
        inner = "".join(lxml.etree.tostring(child, encoding="unicode") for child in div)
        d = pq(f"<div>{inner}</div>", parser="html")
        figures.fix(site, resource, d)
        new_div = lxml.etree.fromstring(
            f'<div xmlns="http://www.w3.org/1999/xhtml">{d.html()}</div>'
        )
        c.remove(div)
        c.append(new_div)
    if site.mode.production:
        hashing.rewrite(site, root)
    return lxml.etree.tostring(
        root.getroottree(), xml_declaration=True, encoding="UTF-8"
    ).decode("utf-8")

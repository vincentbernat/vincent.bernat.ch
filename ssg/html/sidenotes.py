"""Turn footnotes into sidenotes."""

from typing import TYPE_CHECKING

from pyquery import PyQuery as pq

if TYPE_CHECKING:
    import lxml.etree
    from pyquery import PyQuery

# Elements with margin-top. Sidenotes can be inserted before them.
MARGIN_TOP_TAGS = frozenset({"p", "dl", "h1", "h2", "h3", "h4"})
MARGIN_TOP_CLASSES = frozenset(
    {"codehilite", "admonition", "toc", "lf-table", "lf-media-outer", "lf-listing"}
)


def has_margin_top(el: lxml.etree._Element) -> bool:
    if el.tag in MARGIN_TOP_TAGS:
        return True
    classes = (el.get("class") or "").split()
    return bool(MARGIN_TOP_CLASSES.intersection(classes))


def convert(d: PyQuery) -> None:
    """Move footnotes to sidenotes.

    The footnote extension uses the following classes:
    - .footnote: the ordered list of footnotes, to be removed
    - .footnote-ref: the link to the footnote, renamed to .lf-sidenote-ref
    - .footnote-backref: the link at the end of footnote to go back to the
      reference

    And we add:
    - .lf-sidenote-refmark: the reference mark before the sidenote
    - .lf-sidenote-end: replace the backref link
    """
    for cls in ["footnote-ref", "footnote-backref"]:
        els = d(f".{cls}")
        els.removeClass(cls)
        els.addClass(cls.replace("foot", "lf-side"))

    notes = d(".footnote ol")

    # Pop out backrefs when they are the only element of their container.
    for backref in notes(".lf-sidenote-backref"):
        parent = backref.getparent()
        if len(pq(parent).contents()) == 1:
            backref.tail = parent.tail
            parent.getparent().replace(parent, backref)

    # Create sidenotes and insert them after their parent.
    for ref in d.items("sup[id^='fnref:']"):
        name = ref.attr.id[6:]
        fn = notes(f"li[id='fn:{name}']")
        assert fn, f"sidenote {name} does not exist"
        parents = ref.parents()
        for i in range(len(parents) - 1):
            if parents.eq(i).has_class("lf-text"):
                parent = parents.eq(i + 1)
        sidenote = pq("<aside>")
        sidenote.attr.role = "note"
        sidenote.attr.class_ = "lf-sidenote"
        sidenote.attr.id = f"sidenote-{name}"
        ref[0].set("data-anchor", f"--lf-sn-{name}")
        sidenote[0].set("data-anchor", f"--lf-sn-{name}")
        refmark = sidenote[0].makeelement("sup", {"class": "lf-sidenote-refmark"})
        refmark.text = ref.text()
        refmark.tail = fn[0].text
        sidenote[0].append(refmark)
        sidenote[0].extend(list(fn[0]))
        for backref in sidenote("a.lf-sidenote-backref").items():
            backref[0].tag = "span"
            backref[0].attrib.clear()
            backref[0].set("class", "lf-sidenote-end")
        ref("a.lf-sidenote-ref").attr.href = f"#sidenote-{name}"
        insert_point = parent
        # Skip past following siblings without margin-top
        next_el = insert_point[0].getnext()
        while next_el is not None and not has_margin_top(next_el):
            insert_point = pq(next_el)
            next_el = next_el.getnext()
        sidenote.insert_after(insert_point)

    d(".footnote").remove()

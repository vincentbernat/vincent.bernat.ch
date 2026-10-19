"""Turn footnotes into sidenotes."""

from typing import TYPE_CHECKING

from .dom import add_class, classes, remove, remove_class, select, text

if TYPE_CHECKING:
    import lxml.etree

# Elements with margin-top. Sidenotes can be inserted before them.
MARGIN_TOP_TAGS = frozenset({"p", "dl", "h1", "h2", "h3", "h4"})
MARGIN_TOP_CLASSES = frozenset(
    {"codehilite", "admonition", "toc", "lf-table", "lf-media-outer", "lf-listing"}
)


def has_margin_top(el: lxml.etree._Element) -> bool:
    if el.tag in MARGIN_TOP_TAGS:
        return True
    return bool(MARGIN_TOP_CLASSES.intersection(classes(el)))


def convert(root: lxml.etree._Element) -> None:
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
        for el in select(root, f".{cls}"):
            remove_class(el, cls)
            add_class(el, cls.replace("foot", "lf-side"))

    notes = select(root, ".footnote ol")

    # Pop out backrefs when they are the only element of their container.
    for backref in [el for ol in notes for el in select(ol, ".lf-sidenote-backref")]:
        container = backref.getparent()
        assert container is not None
        grandparent = container.getparent()
        if (
            grandparent is not None
            and len(container.xpath("child::text()|child::*")) == 1
        ):
            backref.tail = container.tail
            grandparent.replace(container, backref)

    # Create sidenotes and insert them after their parent.
    for ref in select(root, "sup[id^='fnref:']"):
        name = ref.get("id", "")[6:]
        fn = [el for ol in notes for el in select(ol, f"li[id='fn:{name}']")]
        assert fn, f"sidenote {name} does not exist"
        parents = list(ref.iterancestors())[::-1]
        for i in range(len(parents) - 1):
            if "lf-text" in classes(parents[i]):
                parent = parents[i + 1]
        sidenote = ref.makeelement(
            "aside",
            {
                "role": "note",
                "class": "lf-sidenote",
                "id": f"sidenote-{name}",
                "data-anchor": f"--lf-sn-{name}",
            },
        )
        ref.set("data-anchor", f"--lf-sn-{name}")
        refmark = sidenote.makeelement("sup", {"class": "lf-sidenote-refmark"})
        refmark.text = text(ref)
        refmark.tail = fn[0].text
        sidenote.append(refmark)
        sidenote.extend(list(fn[0]))
        for backref in select(sidenote, "a.lf-sidenote-backref"):
            backref.tag = "span"
            backref.attrib.clear()
            backref.set("class", "lf-sidenote-end")
        for link in select(ref, "a.lf-sidenote-ref"):
            link.set("href", f"#sidenote-{name}")
        insert_point = parent
        # Skip past following siblings without margin-top
        next_el = insert_point.getnext()
        while next_el is not None and not has_margin_top(next_el):
            insert_point = next_el
            next_el = next_el.getnext()
        insert_point.addnext(sidenote)

    for el in select(root, ".footnote"):
        remove(el)

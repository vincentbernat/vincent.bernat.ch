import re

from pyquery import PyQuery as pq
from hyde.plugin import Plugin


class FootnotesPlugin(Plugin):
    """Move footnotes to sidenotes."""

    @classmethod
    def _has_margin_top(cls, el):
        """Check if an element has margin-top in CSS."""
        # These are the elements with margin-top. We can insert sidenotes before them.
        MARGIN_TOP_TAGS = frozenset({"p", "dl", "h1", "h2", "h3", "h4"})
        MARGIN_TOP_CLASSES = frozenset(
            {
                "codehilite",
                "admonition",
                "toc",
                "lf-table",
                "lf-media-outer",
                "lf-listing",
            }
        )

        if el.tag in MARGIN_TOP_TAGS:
            return True
        classes = (el.get("class") or "").split()
        return bool(MARGIN_TOP_CLASSES.intersection(classes))

    def text_resource_complete(self, resource, text):
        if resource.source_file.kind != "html":
            return
        d = pq(text, parser="html")

        # The footnote extension uses the following classes:
        # - .footnote: the ordered list of footnotes, to be removed
        # - .footnote-ref: the link to the footnote, renamed to .lf-sidenote-ref
        # - .footnote-backref: the link at the end of footnote to go back to the
        #   reference
        #
        # And we add:
        # - .lf-sidenote-refmark: the reference mark before the sidenote
        # - .lf-sidenote-end: replace the backref link

        # Rename footnote to sidenote
        for cls in ["footnote-ref", "footnote-backref"]:
            els = d(f".{cls}")
            els.removeClass(cls)
            els.addClass(cls.replace("foot", "lf-side"))

        sidenotes = d(".footnote ol")

        # Pop out backrefs when they are the only element of their container.
        backrefs = sidenotes(".lf-sidenote-backref")
        for backref in backrefs.items():
            parent = backref.parent()
            if len(parent.contents()) == 1:
                parent.replace_with(backref)

        # Create sidenotes and insert them after their parent.
        for ref in d.items("sup[id^='fnref:']"):
            name = ref.attr.id[6:]
            fn = sidenotes(f"li[id='fn:{name}']")
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
            sidenote.html(
                f'<sup class="lf-sidenote-refmark">{ref.text()}</sup>{fn.html()}'
            )
            for backref in sidenote("a.lf-sidenote-backref").items():
                backref[0].tag = "span"
                backref[0].attrib.clear()
                backref[0].set("class", "lf-sidenote-end")
            ref("a.lf-sidenote-ref").attr.href = f"#sidenote-{name}"
            insert_point = parent
            # Skip past following siblings without margin-top
            next_el = insert_point[0].getnext()
            while next_el is not None and not self._has_margin_top(next_el):
                insert_point = pq(next_el)
                next_el = next_el.getnext()
            sidenote.insert_after(insert_point)

        # Remove footnote section
        d(".footnote").remove()

        return "<!DOCTYPE html>\n" + d.outer_html()


class TOCPlugin(Plugin):
    """Remove whitespaces inside UL and add a disclosure to expand the TOC"""

    def text_resource_complete(self, resource, text):
        if resource.source_file.kind != "html":
            return
        d = pq(text, parser="html")
        for toc in d.items(".toc"):
            # The empty details element is only a switch: CSS uses its state to
            # display the TOC collapsed or expanded. It never hides anything.
            toc.prepend(
                "<details>"
                f'<summary aria-label="{resource.meta.l10n.toc}"></summary>'
                "</details>"
            )
            html = toc.outer_html()
            html = re.sub(r"</li>\s+</ul>", "</li></ul>", html)
            toc.replace_with(html)
        return "<!DOCTYPE html>\n" + d.outer_html()

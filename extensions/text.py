import re
import subprocess
import html

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

        # Rename footnote to sidenote
        for cls in ["footnote-ref", "footnote-backref"]:
            els = d(f".{cls}")
            els.removeClass(cls)
            els.addClass(cls.replace("foot", "side"))

        sidenotes = d(".footnote ol")

        # Pop out orphaned backlinks
        backrefs = sidenotes(".sidenote-backref")
        for backref in backrefs.items():
            parent = backref.parent()
            if len(parent.contents()) == 1:
                # We only have the <a> link
                parent.replace_with(backref)

        # Create sidenotes and insert them after their parent.
        for ref in d.items("sup[id^=fnref-]"):
            name = ref.attr.id[6:]
            fn = sidenotes("li[id=fn-{}]".format(name))
            assert fn
            parents = ref.parents()
            for i in range(len(parents) - 1):
                if parents.eq(i).attr.id == "lf-text":
                    parent = parents.eq(i + 1)
            sidenote = pq("<aside>")
            sidenote.attr.role = "note"
            sidenote.attr.class_ = "lf-sidenote"
            sidenote.attr.id = "sidenote-{}".format(name)
            ref[0].set("style", "anchor-name: --fn-{}".format(name))
            sidenote[0].set("style", "position-anchor: --fn-{}".format(name))
            sidenote.html(
                '<sup class="lf-refmark">{}</sup>{}'.format(ref.text(), fn.html())
            )
            for backref in sidenote("a.sidenote-backref").items():
                backref[0].tag = "span"
                backref[0].attrib.clear()
                backref[0].set("class", "sidenote-end")
            ref("a.sidenote-ref").attr.href = "#sidenote-{}".format(name)
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


class LatexPlugin(Plugin):
    """Transform LaTeX formula with KaTeX."""

    JS = """
var katex = require('katex');
var split = require('split');
process.stdin.pipe(split('\\0', null, { trailing: false })).on('data', function(latex) {
  process.stdout.write(katex.renderToString(latex));
  process.stdout.write('\\0');
});
"""
    RE = re.compile(r"(?<!\\)·(.+?)·", re.DOTALL)
    PR = None

    def katex_render(self, mo):
        formula = html.unescape(mo.group(1))
        if self.PR is None:
            self.PR = subprocess.Popen(
                ["node", "-e", self.JS], stdin=subprocess.PIPE, stdout=subprocess.PIPE
            )
        # Assume input is small enough
        self.PR.stdin.write(formula.encode("utf-8"))
        self.PR.stdin.write(b"\0")
        self.PR.stdin.flush()
        # Get answer
        answer = b""
        while True:
            char = self.PR.stdout.read(1)
            if char == b"":
                raise RuntimeError("unexpected stream end")
            if char == b"\0":
                break
            answer += char
        answer = answer.decode("utf-8")
        return answer

    def text_resource_complete(self, resource, text):
        if resource.source_file.kind != "html":
            return
        return self.RE.sub(self.katex_render, text)

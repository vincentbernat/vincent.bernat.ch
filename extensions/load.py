import os.path

from pyquery import PyQuery as pq
from lxml.html import fragment_fromstring
from hyde.plugin import Plugin


class LoadPlugin(Plugin):
    """Load needed scripts/CSS."""

    @staticmethod
    def _insert_after(anchor, tags):
        # Insert the tags right after the anchor element, keeping a 2-space
        # indentation. The anchor's original tail is preserved on the last tag.
        # If we didn't care about indentations, we could just use "for tag in
        # tags: anchor.after(tag)".
        if not anchor or not tags:
            return
        el = anchor[0]
        orig_tail = el.tail
        el.tail = "\n  "
        for i, tag in enumerate(reversed(tags)):
            new = fragment_fromstring(tag)
            new.tail = orig_tail if i == 0 else "\n  "
            el.addnext(new)

    def text_resource_complete(self, resource, text):
        if not resource.source_file.kind == "html":
            return

        d = pq(text, parser="html")
        css_anchor = d(f'link[href="{self.site.media_url("css/luffy.css")}"]')
        js_anchor = d(f'script[src="{self.site.media_url("js/luffy.js")}"]')
        css_tags = []
        js_tags = []

        for target in self.site.config.load:
            if not d(target.selector):
                continue
            files = target.files
            if not isinstance(files, list):
                files = [files]
            lazy = target.get("lazy", False)
            for f in files:
                src = self.site.media_url(f)
                name = os.path.basename(f)
                if f.endswith(".css"):
                    if lazy:
                        css_tags.append(
                            f'<link rel="stylesheet" data-href="{src}" '
                            f'data-name="{name}" href="data:text/css;base64,">'
                        )
                    else:
                        css_tags.append(f'<link rel="stylesheet" href="{src}">')
                else:
                    if lazy:
                        js_tags.append(
                            f'<script data-src="{src}" data-name="{name}"></script>'
                        )
                    else:
                        js_tags.append(f'<script src="{src}" type="module"></script>')

        self._insert_after(css_anchor, css_tags)
        self._insert_after(js_anchor, js_tags)

        return "<!DOCTYPE html>\n" + d.outer_html()

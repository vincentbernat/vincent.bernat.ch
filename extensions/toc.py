import re
from pyquery import PyQuery as pq
from hyde.plugin import Plugin


class FixTOC(Plugin):
    """Remove whitespaces inside UL"""

    def text_resource_complete(self, resource, text):
        if not resource.source_file.kind == "html":
            return
        d = pq(text, parser="html")
        for toc in d.items(".toc"):
            html = toc.outer_html()
            html = re.sub(r"</li>\s+</ul>", "</li></ul>", html)
            toc.replace_with(html)
        return "<!DOCTYPE html>\n" + d.outer_html()

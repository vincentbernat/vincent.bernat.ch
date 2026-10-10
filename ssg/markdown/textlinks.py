"""Links to other files of the site.

[[en/blog/foo.html]] is the URL of a page, [[!!images/foo.png]] the URL of a
media file. They work anywhere, including inside HTML, but not in fenced code
blocks.
"""

import re

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor


class TextLinksExtension(Extension):
    def __init__(self, site):
        super().__init__()
        self.site = site

    def extendMarkdown(self, md):
        md.registerExtension(self)
        # After fenced code blocks (25) and before raw HTML (20) are put aside
        md.preprocessors.register(TextLinksPreprocessor(md, self.site), "textlinks", 22)


class TextLinksPreprocessor(Preprocessor):
    CONTENT_RE = re.compile(r"\[\[([^\]^! ][^\]]*)\]\]")
    MEDIA_RE = re.compile(r"\[\[\!\!([^\]]*)\]\]")

    def __init__(self, md, site):
        super().__init__(md)
        self.site = site

    def run(self, lines):
        text = "\n".join(lines)
        text = self.CONTENT_RE.sub(lambda m: self.site.content_url(m.group(1)), text)
        text = self.MEDIA_RE.sub(lambda m: self.site.media_url(m.group(1)), text)
        return text.split("\n")


def makeExtension(site):
    return TextLinksExtension(site)

"""Remove HTML comments from Markdown."""

import re

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from markdown.util import HTML_PLACEHOLDER


class HTMLCommentsExtension(Extension):
    def extendMarkdown(self, md):
        md.registerExtension(self)
        md.preprocessors.register(HTMLCommentsPreprocessor(md), "html_comments", 15)


class HTMLCommentsPreprocessor(Preprocessor):
    COMMENT_RE = re.compile(r"\A\s*<!--.*?-->\s*\Z", re.DOTALL)

    def run(self, lines):
        removed = set()
        for i, html in enumerate(self.md.htmlStash.rawHtmlBlocks):
            if self.COMMENT_RE.match(html):
                self.md.htmlStash.rawHtmlBlocks[i] = ""
                removed.add(HTML_PLACEHOLDER % i)
        if removed:
            lines = [l for l in lines if l.strip() not in removed]
        return lines


def makeExtension(*args, **kwargs):
    return HTMLCommentsExtension(*args, **kwargs)

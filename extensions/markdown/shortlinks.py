"""Add additional schemas for URL."""

import re

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor


class ShortLinksExtension(Extension):
    def extendMarkdown(self, md, md_globals):
        md.registerExtension(self)
        md.preprocessors.add("shortlinks", ShortLinksPreprocessor(md), "<reference")


class ShortLinksPreprocessor(Preprocessor):
    SCHEMAS = {"rfc": "https://www.rfc-editor.org/rfc/rfc{}"}
    RE = re.compile(rf"({'|'.join(SCHEMAS.keys())})://(\w+)", re.ASCII)

    def run(self, lines):
        return [
            self.RE.sub(lambda mo: self.SCHEMAS[mo.group(1)].format(mo.group(2)), l)
            for l in lines
        ]


def makeExtension(*args, **kwargs):
    return ShortLinksExtension(*args, **kwargs)

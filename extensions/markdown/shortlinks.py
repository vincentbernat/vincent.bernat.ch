"""Add additional schemas for URL."""

import functools
import gzip
import json
import os
import re

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

# Built and symlinked here by flake.nix.
RFC_INDEX = os.path.join(os.path.dirname(__file__), "rfc-index.json.gz")


@functools.cache
def rfc_titles():
    """Map RFC numbers to their titles."""
    with gzip.open(RFC_INDEX, "rt", encoding="utf-8") as f:
        return json.load(f)


class ShortLinksExtension(Extension):
    def __init__(self, **kwargs):
        self.config = {"l10n": [{}, "Translated strings, from the resource meta"]}
        super().__init__(**kwargs)

    def extendMarkdown(self, md):
        md.registerExtension(self)
        md.preprocessors.register(
            ShortLinksPreprocessor(md, self.getConfig("l10n")), "shortlinks", 12
        )


class ShortLinksPreprocessor(Preprocessor):
    SCHEMAS = {
        "rfc": "https://www.rfc-editor.org/rfc/rfc{}",
        "man": "https://manpages.debian.org/{}.html",
        "doi": "https://oadoi.org/{}",
        "sci-hub": "https://sci-hub.fr/{}",
        "go": "https://pkg.go.dev/{}",
    }
    RE = re.compile(rf"({'|'.join(SCHEMAS.keys())})://([\w.~;=:@+/-]+)", re.ASCII)

    # Links without a title: a reference definition or an inline link.
    DEFINITION_RE = re.compile(r"^(?P<prefix>\[[^]]+\]:[ \t]*)(?P<url>\S+)[ \t]*$")
    INLINE_RE = re.compile(r"(?P<prefix>\]\()(?P<url>[^\s()]+)\)")

    # Links we can build a title for.
    RFC_RE = re.compile(r"^https://www\.rfc-editor\.org/rfc/rfc(\d+)(?:#.*)?$")
    MANPAGE_RE = re.compile(
        r"^https://manpages\.debian\.org/(?:[^/]+/)*([\w.+-]+)\.(\d\w*)\.html(?:#.*)?$"
    )
    GODOC_RE = re.compile(r"^https://pkg\.go\.dev/([^#?]+?)/?(?:#([^#]*))?$")

    def __init__(self, md, l10n):
        super().__init__(md)
        self.l10n = l10n

    def title(self, url):
        """Build a title from an RFC, a manual page or a Go package URL."""
        if not self.l10n:
            return None
        mo = self.RFC_RE.match(url)
        if mo:
            number = mo.group(1)
            title = rfc_titles().get(number)
            if title is None:
                return None
            return self.l10n.rfc.format(number, title)
        mo = self.MANPAGE_RE.match(url)
        if mo:
            return self.l10n.manpage.format(f"{mo.group(1)}({mo.group(2)})")
        mo = self.GODOC_RE.match(url)
        if mo:
            path, symbol = mo.group(1), mo.group(2)
            version = None
            if "@" in path:
                # Inside a module, the package path is written with dots.
                module, _, rest = path.partition("@")
                version, _, subpath = rest.partition("/")
                path = ".".join(p for p in (module, subpath.replace("/", ".")) if p)
            name = ".".join(p for p in (path, symbol) if p)
            if version:
                name = f"{name} ({version})"
            return self.l10n.godoc.format(name)
        return None

    def expand(self, mo):
        return self.SCHEMAS[mo.group(1)].format(mo.group(2))

    def add_title(self, mo, suffix=""):
        title = self.title(mo.group("url"))
        if title is None:
            return mo.group(0)
        return f'{mo.group("prefix")}{mo.group("url")} "{title}"{suffix}'

    def run(self, lines):
        lines = [self.RE.sub(self.expand, l) for l in lines]
        lines = [self.DEFINITION_RE.sub(self.add_title, l) for l in lines]
        return [
            self.INLINE_RE.sub(lambda mo: self.add_title(mo, ")"), l) for l in lines
        ]


def makeExtension(*args, **kwargs):
    return ShortLinksExtension(*args, **kwargs)

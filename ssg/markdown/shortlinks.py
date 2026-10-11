"""Add additional schemas for URL."""

from __future__ import annotations

import functools
import gzip
import json
import os
import re
from typing import TYPE_CHECKING, Any, ClassVar

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

if TYPE_CHECKING:
    from ..model.meta import Meta

# Built and symlinked here by flake.nix.
RFC_INDEX = os.path.join(os.path.dirname(__file__), "rfc-index.json.gz")


@functools.cache
def rfc_titles() -> dict[str, str]:
    """Map RFC numbers to their titles."""
    with gzip.open(RFC_INDEX, "rt", encoding="utf-8") as f:
        return json.load(f)


class ShortLinksExtension(Extension):
    def __init__(self, **kwargs: Any) -> None:
        self.config = {
            "l10n": [{}, "Translated strings, from the resource meta"],
            "sources": ["", "URL of the sources of the site, from the resource meta"],
        }
        super().__init__(**kwargs)

    def extendMarkdown(self, md: Any) -> None:
        md.registerExtension(self)
        md.preprocessors.register(
            ShortLinksPreprocessor(
                md, self.getConfig("l10n"), self.getConfig("sources")
            ),
            "shortlinks",
            12,
        )


class ShortLinksPreprocessor(Preprocessor):
    SCHEMAS: ClassVar[dict[str, str]] = {
        "rfc": "https://www.rfc-editor.org/rfc/rfc{}",
        "man": "https://manpages.debian.org/{}.html",
        "doi": "https://oadoi.org/{}",
        "sci-hub": "https://sci-hub.fr/{}",
        "go": "https://pkg.go.dev/{}",
        # A directory ends with a slash. "@commit/" can come first.
        "src": "{sources}/{kind}/{ref}/{path}",
    }
    RE = re.compile(rf"({'|'.join(SCHEMAS.keys())})://([\w.~;=:@+/-]+)", re.ASCII)

    SRC_REF_RE = re.compile(r"@(?P<ref>[0-9a-f]{7,40})(?:/(?P<path>.*))?")

    # Links without a title: a reference definition or an inline link.
    DEFINITION_RE = re.compile(r"^(?P<prefix>\[[^]]+\]:[ \t]*)(?P<url>\S+)[ \t]*$")
    INLINE_RE = re.compile(r"(?P<prefix>\]\()(?P<url>[^\s()]+)\)")

    # Links we can build a title for.
    RFC_RE = re.compile(r"^https://www\.rfc-editor\.org/rfc/rfc(\d+)(?:#.*)?$")
    MANPAGE_RE = re.compile(
        r"^https://manpages\.debian\.org/(?:[^/]+/)*([\w.+-]+)\.(\d\w*)\.html(?:#.*)?$"
    )
    GODOC_RE = re.compile(r"^https://pkg\.go\.dev/([^#?]+?)/?(?:#([^#]*))?$")

    def __init__(self, md: Any, l10n: Meta | None, sources: str | None) -> None:
        super().__init__(md)
        self.l10n = l10n
        self.sources = sources

    def title(self, url: str) -> str | None:
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

    def expand(self, mo: re.Match[str]) -> str:
        schema, path = mo.groups()
        if schema == "src":
            if not self.sources:
                raise ValueError(f"{mo.group(0)}: no sources in metadata")
            ref = "main"
            if m := self.SRC_REF_RE.fullmatch(path):
                ref, path = m.group("ref", "path")
                if path is None:
                    return f"{self.sources}/commit/{ref}"
            return self.SCHEMAS[schema].format(
                sources=self.sources,
                kind="tree" if path.endswith("/") else "blob",
                ref=ref,
                path=path.rstrip("/"),
            )
        return self.SCHEMAS[schema].format(path)

    def add_title(self, mo: re.Match[str], suffix: str = "") -> str:
        title = self.title(mo.group("url"))
        if title is None:
            return mo.group(0)
        return f'{mo.group("prefix")}{mo.group("url")} "{title}"{suffix}'

    def run(self, lines: list[str]) -> list[str]:
        lines = [self.RE.sub(self.expand, l) for l in lines]
        lines = [self.DEFINITION_RE.sub(self.add_title, l) for l in lines]
        return [
            self.INLINE_RE.sub(lambda mo: self.add_title(mo, ")"), l) for l in lines
        ]


def makeExtension(*args: Any, **kwargs: Any) -> ShortLinksExtension:
    return ShortLinksExtension(*args, **kwargs)

"""Resources: files of the content."""

from __future__ import annotations

import fnmatch
import functools
import posixpath
from pathlib import Path
from typing import TYPE_CHECKING

from .. import config, deps
from .meta import FRONTMATTER, Meta, digest

if TYPE_CHECKING:
    from .node import Node
    from .site import Site

PYTHON = "#!python\n"


def read_content(path: Path) -> str | None:
    """Content of a text file, None for a binary file."""
    chunks = []
    with path.open("rb") as f:
        while chunk := f.read(65536):
            if b"\0" in chunk:
                return None
            chunks.append(chunk)
    return b"".join(chunks).decode("utf-8")


class Resource:
    def __init__(
        self, site: Site, node: Node, path: str, source: Path | None = None
    ) -> None:
        self.site = site
        self.node = node
        self.path = path
        self.source = source or config.CONTENT / path
        self.name = posixpath.basename(path)
        self.stem, ext = posixpath.splitext(self.name)
        self.kind = ext.lstrip(".")
        self.simple_copy = any(fnmatch.fnmatch(path, p) for p in config.SIMPLE_COPY)
        # Text of the source, None for binary files and files copied as is
        self.content = None if self.simple_copy else read_content(self.source)
        self.text = self.content is not None
        self.processable = True
        self.python = False
        self.meta = Meta()
        self.combined: list[Resource] = []
        self._translations: list[Resource] = []
        self.neighbors: dict[str, Resource] = {}
        self.tags: list[str] = []

    def __repr__(self) -> str:
        return self.path

    @property
    def url(self) -> str:
        return "/" + self.path

    @property
    def uses_template(self) -> bool:
        return self.meta.get("uses_template", True)

    @property
    def translations(self) -> list[Resource]:
        for translation in self._translations:
            deps.record_resource(translation)
        return self._translations

    def neighbor(self, attr: str) -> Resource | None:
        other = self.neighbors.get(attr)
        deps.record(f"n:{self.path}:{attr}", other.digest if other else "")
        return other

    def prev(self, sorter: str) -> Resource | None:
        return self.neighbor(f"prev_by_{sorter}")

    def next(self, sorter: str) -> Resource | None:
        return self.neighbor(f"next_by_{sorter}")

    def cover_image(self) -> str:
        """Path of the cover image, relative to media."""
        return "images/covers/" + posixpath.splitext(self.path)[0] + ".jpg"

    @property
    def media_path(self) -> str:
        """Path relative to the media directory."""
        return self.path.removeprefix("media/")

    @property
    def post(self) -> bool:
        """Blog posts are listed. Other pages may display their article."""
        return self.meta.get("listable") is True

    @functools.cached_property
    def digest(self) -> str:
        """Digest of what other pages may display about this resource."""
        return digest(
            [
                self.url,
                self.meta,
                list(self.tags),
                [(t.url, t.meta.language) for t in self._translations],
            ]
        )

    @property
    def source_text(self) -> str:
        """Content of a text resource."""
        if self.content is None:
            raise ValueError(f"{self.path} is not a text file")
        return self.content

    def body(self) -> str:
        """Source text without frontmatter."""
        text = self.source_text
        match = FRONTMATTER.match(text)
        if match:
            text = text[match.end() :]
        return text or " "

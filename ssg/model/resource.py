"""Resources: files of the content."""

import fnmatch
import functools
import os

from .. import config, deps
from .meta import FRONTMATTER, digest

PYTHON = "#!python\n"


def read_content(path):
    """Content of a text file, None for a binary file."""
    chunks = []
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            if b"\0" in chunk:
                return None
            chunks.append(chunk)
    return b"".join(chunks).decode("utf-8")


class Resource:
    def __init__(self, site, node, path):
        self.site = site
        self.node = node
        self.path = path
        self.source = config.CONTENT / path
        self.name = self.source.name
        self.stem, ext = os.path.splitext(self.name)
        self.kind = ext.lstrip(".")
        self.simple_copy = any(fnmatch.fnmatch(path, p) for p in config.SIMPLE_COPY)
        # Text of the source, None for binary files and files copied as is
        self.content = None if self.simple_copy else read_content(self.source)
        self.text = self.content is not None
        self.processable = True
        self.python = False
        self.meta = None
        self.combined = []
        self._translations = []
        self.neighbors = {}
        self.tags = []

    def __repr__(self):
        return self.path

    @property
    def url(self):
        return "/" + self.path

    @property
    def uses_template(self):
        return self.meta.get("uses_template", True)

    @property
    def translations(self):
        for translation in self._translations:
            deps.record_resource(translation)
        return self._translations

    def neighbor(self, attr):
        other = self.neighbors.get(attr)
        deps.record(f"n:{self.path}:{attr}", other.digest if other else "")
        return other

    def prev(self, sorter):
        return self.neighbor(f"prev_by_{sorter}")

    def next(self, sorter):
        return self.neighbor(f"next_by_{sorter}")

    def cover_image(self):
        """Path of the cover image, relative to media."""
        return "images/covers/" + os.path.splitext(self.path)[0] + ".jpg"

    @property
    def media_path(self):
        """Path relative to the media directory."""
        return self.path.removeprefix("media/")

    @property
    def post(self):
        """Blog posts are listed. Other pages may display their article."""
        return self.meta.get("listable") is True

    @functools.cached_property
    def digest(self):
        """Digest of what other pages may display about this resource."""
        return digest(
            [
                self.url,
                self.meta,
                list(self.tags),
                [(t.url, t.meta.language) for t in self._translations],
            ]
        )

    def body(self):
        """Source text without frontmatter."""
        text = self.content
        match = FRONTMATTER.match(text)
        if match:
            text = text[match.end() :]
        return text or " "

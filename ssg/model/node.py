"""Nodes: directories of the content, with sorted resources."""

import functools
from operator import attrgetter

from .. import config, deps
from .meta import digest


class Node:
    def __init__(self, site, path, parent):
        self.site = site
        self.path = path
        self.source = config.CONTENT / path if path else config.CONTENT
        self.parent = parent
        self.children = []
        self.resources = []
        self.meta = None

    def __repr__(self):
        return str(self.source)

    def walk(self):
        yield self
        for child in sorted(self.children, key=lambda n: str(n.source)):
            yield from child.walk()

    def walk_resources(self):
        for node in self.walk():
            yield from sorted(node.resources, key=lambda r: str(r.source))

    def sorted(self, name):
        """Resources of this node, sorted with the given sorter."""
        deps.record(f"w:{self.path}:{name}", self.sorted_digest(name))
        return self._sorted(name)

    def all_resources(self):
        """Resources of this node and its descendants, in walk order."""
        return self.sorted("all")

    @functools.cache
    def _sorted(self, name):
        if name == "all":
            return list(self.walk_resources())
        attrs, reverse, filters = SORTERS[name]
        result = []
        for resource in self.walk_resources():
            try:
                attrgetter(*attrs)(resource)
            except AttributeError:
                continue
            if all(
                getattr_path(resource, field) == value
                for field, value in filters.items()
            ):
                result.append(resource)
        return sorted(result, key=attrgetter(*attrs), reverse=reverse)

    @functools.cache
    def sorted_digest(self, name):
        return digest([(r.path, r.digest) for r in self._sorted(name)])


def getattr_path(obj, field):
    try:
        return attrgetter(field)(obj)
    except AttributeError:
        return None


# Sorters: attributes to sort on, reverse order, filters, circular links
HTML_LISTABLE = {"kind": "html", "meta.listable": True}
SORTERS = {
    "name": (["path"], False, {}),
    "time": (["meta.created"], True, HTML_LISTABLE),
    "time_en": (
        ["meta.created", "path"],
        True,
        HTML_LISTABLE | {"meta.language": "en"},
    ),
    "time_fr": (
        ["meta.created", "path"],
        True,
        HTML_LISTABLE | {"meta.language": "fr"},
    ),
    "uuid_en": (["meta.uuid"], False, HTML_LISTABLE | {"meta.language": "en"}),
    "uuid_fr": (["meta.uuid"], False, HTML_LISTABLE | {"meta.language": "fr"}),
}


CIRCULAR = {"uuid_en", "uuid_fr"}

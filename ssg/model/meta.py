"""Metadata, from frontmatter and meta.yaml files."""

import hashlib
import json
import re

FRONTMATTER = re.compile(
    r"^\s*(?:---|===)\s*\n((?:.|\n)+?)\n\s*(?:---|===)\s*\n*", re.MULTILINE
)


def wrap(value):
    if isinstance(value, dict):
        return Meta(value)
    if isinstance(value, list):
        return [wrap(v) for v in value]
    return value


class Meta(dict):
    """Metadata, with attribute access. Keys from a child replace the ones from
    the parent, there is no deep merge."""

    def __init__(self, data=None, parent=None):
        super().__init__()
        if parent:
            self.update(parent)
        for key, value in (data or {}).items():
            self[str(key)] = wrap(value)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(self, name, value):
        self[name] = value


def digest(value):
    data = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha1(data.encode("utf-8")).hexdigest()

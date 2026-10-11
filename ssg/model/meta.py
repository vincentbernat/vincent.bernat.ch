"""Metadata, from frontmatter and meta.yaml files."""

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

FRONTMATTER = re.compile(
    r"^\s*(?:---|===)\s*\n((?:.|\n)+?)\n\s*(?:---|===)\s*\n*", re.MULTILINE
)


def wrap(value: Any) -> Any:
    if isinstance(value, dict):
        return Meta(value)
    if isinstance(value, list):
        return [wrap(v) for v in value]
    return value


class Meta(dict[str, Any]):
    """Metadata, with attribute access. Keys from a child replace the ones from
    the parent, there is no deep merge."""

    def __init__(
        self,
        data: Mapping[Any, Any] | None = None,
        parent: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__()
        if parent:
            self.update(parent)
        for key, value in (data or {}).items():
            self[str(key)] = wrap(value)

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


def digest(value: object) -> str:
    data = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha1(data.encode("utf-8")).hexdigest()

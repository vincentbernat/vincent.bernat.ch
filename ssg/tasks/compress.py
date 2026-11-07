"""Compressed copies of media files, served by the origin (production only)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from .. import deps
from ..tools import run, write

if TYPE_CHECKING:
    from ..model.site import Site

EXTENSIONS = (".css", ".js", ".svg")
COMPRESSORS = {
    ".br": ["brotli", "-c", "-q", "11"],
    ".zst": ["zstd", "-c", "-q", "-19"],
}


def compress(site: Site, path: str) -> None:
    fingerprint = site.fingerprint(path)
    if fingerprint is None:
        raise ValueError(f"{path} is not fingerprinted")
    target = site.output(f"media/{fingerprint['path']}")
    deps.record_file(target)
    for suffix, command in COMPRESSORS.items():
        write(f"{target}{suffix}", run(*command, target, text=False))


def exist(site: Site, path: str) -> bool:
    """Check the compressed copies exist."""
    try:
        name = json.loads(site.manifest(path).read_text())["path"]
    except FileNotFoundError:
        return False
    return all(site.output(f"media/{name}{s}").exists() for s in COMPRESSORS)

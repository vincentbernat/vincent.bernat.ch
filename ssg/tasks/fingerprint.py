"""Fingerprint media files: put a hash of their content in their name."""

from __future__ import annotations

import base64
import hashlib
import json
import posixpath
import re
from pathlib import Path
from typing import TYPE_CHECKING

import xxhash

from ..images import optimize
from ..tools import write
from . import files

if TYPE_CHECKING:
    from ..model.site import Site


def image(site: Site, path: str, manifest: Path) -> None:
    raw = site.raw(path)
    name = site.hashed(path)
    target = site.output(f"media/{name}")
    if site.mode.production:
        outputs = optimize.image(raw, target)
    else:
        files.copy(raw, target)
        outputs = [target]
    names = [o.relative_to(site.output("media")).as_posix() for o in outputs]
    write(manifest, json.dumps({"path": name, "files": names}))


def file(site: Site, path: str, manifest: Path, content: bytes | None = None) -> None:
    if content is None:
        content = site.raw(path).read_bytes()
    digest = xxhash.xxh3_128_hexdigest(content)[:14]
    sha256 = base64.b64encode(hashlib.sha256(content).digest()).decode("ascii")
    root, ext = posixpath.splitext(path)
    name_with_digest = f"{root}.{digest}{ext}"
    names = [name_with_digest]
    if not site.mode.production:
        # Used by pages while the file changes
        names.append(path)
    for n in names:
        write(site.output(f"media/{n}"), content)
    write(
        manifest,
        json.dumps(
            {
                "path": name_with_digest,
                "integrity": f"sha256-{sha256}",
                "files": names,
            }
        ),
    )


CSS_REFERENCE = re.compile(r"[^\s()'\"]*((?:fonts|images)/[^\s()'\"]+)(['\"]?)\)")


def css(site: Site, path: str, manifest: Path) -> None:
    """Use hashed names for fonts and images referenced in a stylesheet."""
    content = site.raw(path).read_text(encoding="utf-8")

    def replace(mo: re.Match[str]) -> str:
        ref = mo.group(1)
        if ref.startswith("fonts/"):
            fingerprint = site.fingerprint(ref)
            if fingerprint is None:
                raise ValueError(f"{path}: unknown font {ref}")
            new = fingerprint["path"]
        else:
            new = site.hashed(ref)
        prefix = mo.group(0)[: mo.start(1) - mo.start(0)]
        return prefix + new + mo.group(2) + ")"

    content = CSS_REFERENCE.sub(replace, content)
    file(site, path, manifest, content.encode("utf-8"))


def exist(site: Site, path: str, manifest: Path) -> bool:
    """Check the files listed in a manifest exist."""
    try:
        files = json.loads(manifest.read_text())["files"]
    except FileNotFoundError:
        return False
    if not site.mode.production and not path.startswith("images/"):
        files.append(path)
    return all(site.output(f"media/{f}").exists() for f in files)

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

from .. import config
from ..images import optimize
from ..tools import run, write
from . import files

if TYPE_CHECKING:
    from ..model.site import Site

# Compressed copies of stylesheets, scripts and SVG images, served by the
# origin in production
PRECOMPRESSED = (".css", ".js", ".svg")
COMPRESSORS = {
    ".br": ["brotli", "-c", "-q", "11"],
    ".zst": ["zstd", "-c", "-q", "-19"],
}


def precompress(target: Path) -> list[Path]:
    """Write compressed copies of target and return them."""
    outputs = []
    for suffix, command in COMPRESSORS.items():
        output = Path(f"{target}{suffix}")
        write(output, run(*command, target, text=False))
        outputs.append(output)
    return outputs


def image(site: Site, path: str, manifest: Path) -> None:
    raw = site.raw(path)
    name = site.hashed(path)
    target = site.output(f"media/{name}")
    # svgo can change how an SVG renders: dev builds use it too
    if site.mode.production or raw.suffix == ".svg":
        outputs = optimize.image(raw, target, config.CONTENT / "media" / path)
    else:
        files.copy(raw, target)
        outputs = [target]
    if site.mode.production and target.suffix in PRECOMPRESSED:
        outputs += precompress(target)
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
    if site.mode.production and ext in PRECOMPRESSED:
        target = site.output(f"media/{name_with_digest}")
        names += [f"{name_with_digest}{o.suffix}" for o in precompress(target)]
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
        data = json.loads(manifest.read_text())
    except FileNotFoundError:
        return False
    files = data["files"]
    if not site.mode.production and not path.startswith("images/"):
        files.append(path)
    if site.mode.production and path.endswith(PRECOMPRESSED):
        files += [f"{data['path']}{suffix}" for suffix in COMPRESSORS]
    return all(site.output(f"media/{f}").exists() for f in files)

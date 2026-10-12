"""Publish media files with a hashed name (production only)."""

from __future__ import annotations

import base64
import hashlib
import json
import posixpath
import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..images import optimize
from ..tools import human, run, write

if TYPE_CHECKING:
    from ..model.site import Site


def image(site: Site, path: str, sidecar: Path) -> None:
    raw = site.raw(path)
    name = site.hashed(path)
    outputs = optimize.image(raw, site.output(f"media/{name}"))
    files = [o.relative_to(site.output("media")).as_posix() for o in outputs]
    write(sidecar, json.dumps({"path": name, "files": files}))


def file(site: Site, path: str, sidecar: Path, content: bytes | None = None) -> None:
    if content is None:
        content = site.raw(path).read_bytes()
    md5 = hashlib.md5(content).hexdigest()[:14]
    sha256 = base64.b64encode(hashlib.sha256(content).digest()).decode("ascii")
    root, ext = posixpath.splitext(path)
    name = f"{root}.{md5}{ext}"
    write(site.output(f"media/{name}"), content)
    write(
        sidecar,
        json.dumps({"path": name, "integrity": f"sha256-{sha256}", "files": [name]}),
    )


CSS_REFERENCE = re.compile(r"[^\s()'\"]*((?:fonts|images)/[^\s()'\"]+)(['\"]?)\)")


def css(site: Site, path: str, sidecar: Path) -> None:
    """Use hashed names for fonts and images referenced in a stylesheet."""
    content = site.raw(path).read_text(encoding="utf-8")

    def replace(mo: re.Match[str]) -> str:
        ref = mo.group(1)
        if ref.startswith("fonts/"):
            published = site.published(ref)
            if published is None:
                raise ValueError(f"{path}: unknown font {ref}")
            new = published["path"]
        else:
            new = site.hashed(ref)
        prefix = mo.group(0)[: mo.start(1) - mo.start(0)]
        return prefix + new + mo.group(2) + ")"

    content = CSS_REFERENCE.sub(replace, content)
    file(site, path, sidecar, content.encode("utf-8"))


def exist(site: Site, sidecar: Path) -> bool:
    """Check the files listed in a sidecar exist."""
    try:
        files = json.loads(sidecar.read_text())["files"]
    except FileNotFoundError:
        return False
    return all(site.output(f"media/{f}").exists() for f in files)


def bundle_sizes(site: Site, bundles: list[str], target: Path) -> None:
    """Sizes of scripts, stylesheets and fonts, with the share of pages using
    them."""
    out = site.mode.output
    sizes = []
    for bundle in bundles:
        raw = site.raw(bundle)
        row = [raw.stat().st_size]
        if bundle.endswith(".woff2"):
            sizes.append((f"media/{bundle}", row * 3))
            continue
        # compression levels are from:
        # https://github.com/NixOS/nixpkgs/blob/master/nixos/modules/services/web-servers/nginx/default.nix
        row += [
            len(run(*compress, raw, text=False))
            for compress in (["gzip", "-c", "-5"], ["brotli", "-c", "-q", "5"])
        ]
        sizes.append((f"media/{bundle}", row))

    # Count pages using each bundle, directly or through a stylesheet
    names = {}
    for bundle in bundles:
        published = site.published(bundle)
        if published is None:
            raise ValueError(f"{bundle} is not published")
        names[published["path"]] = f"media/{bundle}"
    pattern = re.compile(
        rf"(?:{re.escape(site.mode.media_url)}|\.\./)("
        + "|".join(re.escape(name) for name in names)
        + r")(?![\w.-])"
    )

    def references(path: Path) -> set[str]:
        content = path.read_text(encoding="utf-8")
        return {names[name] for name in pattern.findall(content)}

    nested = {
        names[name]: references(out / "media" / name)
        for name in names
        if name.endswith(".css")
    }
    pages = list(out.glob("**/*.html"))
    counts = {f"media/{b}": 0 for b in bundles}
    for page in pages:
        found = references(page)
        for bundle in found.copy():
            found |= nested.get(bundle, set())
        for bundle in found:
            counts[bundle] += 1
    sizes.sort(key=lambda item: (counts[item[0]], item[1][2]), reverse=True)
    totals = []
    for percent in (100, 90, 50, 10, 5, 1):
        rows = [
            row for name, row in sizes if counts[name] * 100 >= percent * len(pages)
        ]
        total = [sum(row[i] for row in rows) for i in range(3)]
        totals.append((f"total ({percent}%)", total))
    totals.append(("total", [sum(row[i] for _, row in sizes) for i in range(3)]))
    sizes += totals
    width = max(len(name) for name, _ in sizes)
    with target.open("w", encoding="utf-8") as f:
        f.write(
            f"{'':<{width}} {'raw':>10} {'gzip':>10} {'brotli':>10} {'pages':>10}\n"
        )
        for name, row in sizes:
            cells = [human(size) for size in row]
            if name.endswith(".woff2"):
                cells[1:] = ["-", "-"]
            if name in counts:
                cells.append(f"{counts[name] * 100 / len(pages):.1f}%")
            columns = "".join(f" {cell:>10}" for cell in cells)
            f.write(f"{name:<{width}}{columns}\n")

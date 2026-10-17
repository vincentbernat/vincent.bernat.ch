"""Sizes of stylesheets, scripts and fonts (production only)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..tools import human, run

if TYPE_CHECKING:
    from ..model.site import Site


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
        fingerprint = site.fingerprint(bundle)
        if fingerprint is None:
            raise ValueError(f"{bundle} is not fingerprinted")
        names[fingerprint["path"]] = f"media/{bundle}"
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

"""Font subsetting (production only)."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from . import markdown
from .tools import run, write

if TYPE_CHECKING:
    from .model.site import Site

KINDS = ("monospace", "regular")

# Fonts to subset, with the glyphs to keep and pyftsubset options. For Iosevka,
# no features needed as there is none except locl, frac, numr, dnom, onum and
# we don't use them.
#
# For Literata, we keep kern since it helps with quality. liga is small. ccmp
# and mark are not used, but may become useful in the future. onum, tnum are
# explicitely used in CSS. lnum and pnum are not needed as lining and
# proportional digits are the default. ss01 (Greek) and ss02 (arrows) are not
# useful. frac, numr, dnom are not used. sups, subs, sinf not useful with HTML.
# smcp, c2sc, case, cpsp, ordn, dlig, zero are not useful. aalt is big.
#
# To look at the result: http://torinak.com/font/lsfont.html
SUBSET = {
    "iosevka": (
        "monospace",
        ["--layout-features=", "--desubroutinize", "--no-hinting"],
    ),
    "literata": (
        "regular",
        ["--layout-features=ccmp,mark,kern,liga,onum,tnum", "--desubroutinize"],
    ),
    "literata-italic": (
        "regular",
        ["--layout-features=ccmp,mark,kern,liga,onum,tnum", "--desubroutinize"],
    ),
}


def glyphs_path(site: Site, kind: str) -> Path:
    return site.mode.cache / f"glyphs-{kind}.txt"


def glyphs(site: Site, fragments: Iterable[Path]) -> None:
    """Collect glyphs used by all articles."""
    result = {kind: set(markdown.base_glyphs()[kind]) for kind in KINDS}
    for fragment in fragments:
        data = json.loads(fragment.read_text(encoding="utf-8"))["glyphs"]
        for kind in KINDS:
            result[kind].update(data[kind])
    for kind in KINDS:
        wanted = sorted(g for g in result[kind] if ord(g) >= 0x20)
        write(glyphs_path(site, kind), "".join(wanted))


def subset(site: Site, name: str, source: Path, target: Path) -> None:
    kind, options = SUBSET[name]
    target.parent.mkdir(parents=True, exist_ok=True)
    run(
        "pyftsubset",
        source,
        "--flavor=woff2",
        f"--text-file={glyphs_path(site, kind)}",
        f"--output-file={target}",
        *options,
    )

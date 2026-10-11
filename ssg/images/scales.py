"""Versions of images for lower pixel densities (foo@1x.jpg from foo@2x.jpg)."""

import re
from pathlib import Path

from PIL import Image

from . import save

PATTERN = re.compile(r".*@(\d+)x\.[^.]*$")


def smaller(path: str) -> list[str]:
    """For an image named foo@Nx.ext, the names of the smaller versions."""
    mo = PATTERN.match(path)
    if not mo:
        return []
    factor = int(mo.group(1))
    return [path.replace(f"@{factor}x.", f"@{f}x.") for f in range(1, factor)]


def resize(source: Path, target: Path, factor: float) -> None:
    im: Image.Image = Image.open(source)
    im = im.resize(
        (int(im.width * factor), int(im.height * factor)), Image.Resampling.LANCZOS
    )
    save(im, target)

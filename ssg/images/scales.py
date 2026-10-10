"""Versions of images for lower pixel densities (foo@1x.jpg from foo@2x.jpg)."""

import re

from PIL import Image

from . import save

PATTERN = re.compile(r".*@(\d+)x\.[^.]*$")


def smaller(path):
    """For an image named foo@Nx.ext, the names of the smaller versions."""
    mo = PATTERN.match(path)
    if not mo:
        return []
    factor = int(mo.group(1))
    return [path.replace(f"@{factor}x.", f"@{f}x.") for f in range(1, factor)]


def resize(source, target, factor):
    im = Image.open(source)
    im = im.resize(
        (int(im.width * factor), int(im.height * factor)), Image.Resampling.LANCZOS
    )
    save(im, target)

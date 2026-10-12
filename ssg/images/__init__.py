"""Images: other versions, properties, covers and optimization."""

from pathlib import Path

from PIL import Image


def save(im: Image.Image, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix == ".jpg":
        im.save(target, "JPEG", quality=100)
    else:
        im.save(target, "PNG")

"""Images: other versions, properties, covers and optimization."""

import os


def save(im, target):
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if str(target).endswith(".jpg"):
        im.save(target, "JPEG", quality=100)
    else:
        im.save(target, "PNG")

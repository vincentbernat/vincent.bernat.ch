"""Functions for templates."""

import os
import tomllib

import jinja2
from markupsafe import Markup

from .. import config, deps
from ..images import thumbnails
from . import jinja_global


@jinja_global
@jinja2.pass_context
def include_file(ctx, name):
    target = os.path.join(ctx["node"].source, name)
    deps.record_file(target)
    with open(target, encoding="utf-8") as f:
        return Markup(f.read())


def as_list(value):
    """Wrap a single string into a list."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return value


@jinja_global
def licenses(lang):
    """List REUSE.toml annotations as (paths, items), items being Markdown."""
    target = config.ROOT / "REUSE.toml"
    deps.record_file(target)
    with open(target, "rb") as f:
        data = tomllib.load(f)
    result = []
    for annotation in data["annotations"]:
        items = []
        for holder in as_list(annotation.get("SPDX-FileCopyrightText")):
            if holder.endswith(">") and " <" in holder:
                name, url = holder[:-1].split(" <", 1)
                items.append(f"[{name}]({url})")
            else:
                items.append(holder)
        license = []
        for token in annotation["SPDX-License-Identifier"].split():
            if token in data["labels"]:
                license.append(data["labels"][token][lang])
            elif token in ("AND", "OR", "WITH"):
                license.append(token)
            else:
                license.append(f"[{token}](https://spdx.org/licenses/{token}.html)")
        items.append(" ".join(license))
        if "note" in annotation:
            items.append(annotation["note"][lang])
        if "source" in annotation:
            items.append(f"[source]({annotation['source']})")
        result.append((as_list(annotation["path"]), items))
    return result


@jinja_global
def thumbnail(image):
    """Thumbnail of an image displayed in a gallery."""
    return thumbnails.info(image)

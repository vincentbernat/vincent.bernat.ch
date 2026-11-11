"""Functions for templates."""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

import jinja2
from markupsafe import Markup

from .. import config, deps
from ..images import thumbnails
from ..model.blogroll import (
    FEEDS,
    Feed,
    FeedArticle,
    favorites,
    published,
    related,
    tag_index,
)
from . import jinja_global

if TYPE_CHECKING:
    from ..model.resource import Resource


@jinja_global
@jinja2.pass_context
def include_file(ctx: jinja2.runtime.Context, name: str) -> Markup:
    target = ctx["node"].source / name
    deps.record_file(target)
    return Markup(target.read_text(encoding="utf-8"))


def as_list(value: str | list[str] | None) -> list[str]:
    """Wrap a single string into a list."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return value


@jinja_global
def licenses(lang: str) -> list[tuple[list[str], list[str]]]:
    """List REUSE.toml annotations as (paths, items), items being Markdown."""
    target = config.ROOT / "REUSE.toml"
    deps.record_file(target)
    with target.open("rb") as f:
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
def blogroll() -> list[tuple[str, list[Feed]]]:
    """Published feeds of feeds.yaml, by category."""
    deps.record_file(FEEDS)
    return published(str(FEEDS))


@jinja_global
def blogroll_favorites(categories: list[tuple[str, list[Feed]]]) -> list[Feed]:
    """Starred feeds of the blogroll, sorted by title."""
    return favorites(categories)


@jinja_global
@jinja2.pass_context
def blogroll_category(ctx: jinja2.runtime.Context, category: str) -> str:
    """Name of a blogroll category in the language of the resource."""
    meta = ctx["resource"].meta
    if meta.language == "en":
        return category
    index = tag_index(category)
    if index is None:
        try:
            return meta.l10n.categories[category]
        except AttributeError, KeyError:
            raise ValueError(
                f"no {meta.language} translation for blogroll category {category}"
            ) from None
    info = list(config.TAGS.values())[index]
    name = str(info.get(f"descr_{meta.language}") or info.get("descr"))
    return name[:1].upper() + name[1:]


@jinja_global
def related_blog(resource: Resource) -> tuple[Feed, FeedArticle | None] | None:
    """A feed of the blogroll related to the tags of a blog post, and one of its
    articles if any."""
    deps.record_file(FEEDS)
    deps.record(f"b:{resource.path}", deps.blogroll_digest(resource))
    found = resource.blogroll_group()
    if found is None:
        return None
    rank, group = found
    seed = resource.meta.get("uuid") or resource.path
    return related(rank, group, resource.meta.language, seed, str(FEEDS))


@jinja_global
def thumbnail(image: Resource) -> thumbnails.Thumb:
    """Thumbnail of an image displayed in a gallery."""
    return thumbnails.info(image)

"""Filters for templates."""

from __future__ import annotations

import html as htmllib
import re
import urllib.parse
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import TYPE_CHECKING

import lxml.etree
import lxml.html
from babel.dates import format_date
from markupsafe import Markup

from .. import deps
from ..html.dom import remove, select, text
from . import jinja_filter

if TYPE_CHECKING:
    from ..model.resource import Resource


@jinja_filter
def urlencode(url: str, safe: str = "/") -> str:
    return urllib.parse.quote(url.encode("utf8"), safe)


@jinja_filter
def date_format(dt: date | None, fmt: str | None = None) -> str | date:
    if not dt:
        dt = datetime.now()  # noqa: DTZ005
        deps.record("y:", str(dt.year))
    if not isinstance(dt, datetime):
        return dt
    return dt.strftime(fmt or "%a, %d %b %Y")


@jinja_filter
def xmldatetime(dt: date | None) -> str:
    if not dt:
        dt = datetime.now()  # noqa: DTZ005
    zprefix = "Z"
    tz = dt.strftime("%z")
    if tz:
        zprefix = tz[:3] + ":" + tz[3:]
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + zprefix


@jinja_filter
def top[T](iterable: Iterable[T], count: int = 3) -> list[T]:
    return list(iterable)[:count]


@jinja_filter
def human_date(dt: date, locale: str = "en", format: str | None = None) -> str:
    """Convert an ISO 8601 date to a more readable version."""
    if format is None:
        return format_date(dt, "MMMM yyyy", locale=locale)
    formatted = format_date(dt, format=format, locale=locale)
    replacements = {}
    if locale == "en":
        return formatted
    elif locale == "fr":
        replacements = {
            1: "1er",
        }
    mo = re.match(r"^(?P<before>.*?)\b(?P<day>\d{1,2})\b(?P<after>.*)$", formatted)
    if mo:
        day_num = int(mo.group("day"))
        if day_num in replacements:
            ordinal = replacements[day_num]
            ordinal_mo = re.match(r"^(\d+)(.+)$", ordinal)
            if ordinal_mo:
                replacement = f"{ordinal_mo.group(1)}<sup>{ordinal_mo.group(2)}</sup>"
                formatted = f"{mo.group('before')}{replacement}{mo.group('after')}"
    return formatted


@jinja_filter
def same_tag(
    resource: Resource, direction: str, sorter: str, skip: int = 0
) -> Resource | None:
    """Returns the next resource with at least a common tag, walking with
    resource.prev() or resource.next()."""
    tags = {t for t in resource.tags if t != "outdated" and t != "unclassified"}
    candidate = resource
    while candidate:
        candidate = getattr(candidate, direction)(sorter)
        if skip:
            skip -= 1
            continue
        ctags = set(candidate.tags) if candidate else set()
        if "outdated" in ctags:
            continue
        if len(tags & ctags) > 0:
            break
    return candidate


NATURAL_RE = re.compile(r"(\d+)")


def natural_key(value: str) -> list[int | str]:
    """Sort key comparing digit runs as numbers."""
    return [
        int(part) if index % 2 else part
        for index, part in enumerate(NATURAL_RE.split(value))
    ]


@jinja_filter
def natural_sort(resources: Iterable[Resource]) -> list[Resource]:
    """Version-sort resources."""
    return sorted(resources, key=lambda r: natural_key(r.path))


@jinja_filter
def mastodon_href(handle: str) -> str:
    """Turn a mastodon handle into an href (very naive)."""
    mo = re.match(r"@(.*)@(.*)", handle)
    assert mo
    return f"https://{mo.group(2)}/@{mo.group(1)}"


@jinja_filter
def in_language(resources: Iterable[Resource], lang: str) -> list[Resource]:
    """Keep resources in lang, or without a translation in lang."""
    return [
        r
        for r in resources
        if r.meta.language == lang
        or lang not in (t.meta.language for t in r.translations)
    ]


@jinja_filter
def tagged(resources: Iterable[Resource], tag: object) -> list[Resource]:
    """Keep resources with tag or one of its subtags. Resources only tagged
    as outdated are part of the unclassified tag."""
    tag = str(tag)
    result = []
    for r in resources:
        tags = [str(t) for t in r.meta.get("tags") or []]
        if any(t == tag or t.startswith(tag + "-") for t in tags) or (
            tag == "unclassified" and tags == ["outdated"]
        ):
            result.append(r)
    return result


@jinja_filter
def tag_tree(tags: Iterable[str]) -> list[tuple[str, list[str]]]:
    """Group tags as (tag, subtags) pairs. Subtags follow their parent."""
    result: list[tuple[str, list[str]]] = []
    for tag in tags:
        if result and tag.startswith(result[-1][0] + "-"):
            result[-1][1].append(tag)
        else:
            result.append((tag, []))
    return result


@jinja_filter
def ai_usage_emoji(entry: str, emojis: Mapping[str, str] | None) -> str | None:
    """Get the emoji for the key matching the start of an AI usage entry."""
    emojis = dict(emojis or {})
    for key, emoji in emojis.items():
        if key != "default" and entry.startswith(key):
            return emoji
    return emojis.get("default")


@jinja_filter
def clean_rss(html: str) -> Markup:
    root = lxml.html.fragment_fromstring(html, create_parent="div")
    for el in select(root, ".when-js, .when-nojs"):
        remove(el)
    for el in select(root, "a"):
        if text(el) == "#":
            remove(el)
    for el in select(root, ".footnote-backref"):
        el[:] = []
        el.text = "↩"
    # Markup so the XHTML markup is inserted into the atom feed as
    # structure rather than autoescaped to entity-encoded text.
    return Markup(
        htmllib.escape(root.text or "", quote=False)
        + "".join(lxml.etree.tostring(el, encoding="unicode") for el in root)
    )

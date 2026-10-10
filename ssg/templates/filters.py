"""Filters for templates."""

import re
import urllib.parse
from datetime import datetime

from babel.dates import format_date
from markupsafe import Markup
from pyquery import PyQuery as pq

from .. import deps
from . import jinja_filter


@jinja_filter
def urlencode(url, safe="/"):
    return urllib.parse.quote(url.encode("utf8"), safe)


@jinja_filter
def date_format(dt, fmt=None):
    if not dt:
        dt = datetime.now()
        deps.record("y:", str(dt.year))
    if not isinstance(dt, datetime):
        return dt
    return dt.strftime(fmt or "%a, %d %b %Y")


@jinja_filter
def xmldatetime(dt):
    if not dt:
        dt = datetime.now()
    zprefix = "Z"
    tz = dt.strftime("%z")
    if tz:
        zprefix = tz[:3] + ":" + tz[3:]
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + zprefix


@jinja_filter
def top(iterable, count=3):
    return list(iterable)[:count]


@jinja_filter
def human_date(dt, locale="en", format=None):
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
def same_tag(resource, direction, sorter, skip=0):
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


def natural_key(value):
    """Sort key comparing digit runs as numbers."""
    return [
        int(part) if index % 2 else part
        for index, part in enumerate(NATURAL_RE.split(value))
    ]


@jinja_filter
def natural_sort(resources):
    """Version-sort resources."""
    return sorted(resources, key=lambda r: natural_key(r.path))


@jinja_filter
def mastodon_href(handle):
    """Turn a mastodon handle into an href (very naive)."""
    mo = re.match(r"@(.*)@(.*)", handle)
    assert mo
    return f"https://{mo.group(2)}/@{mo.group(1)}"


@jinja_filter
def in_language(resources, lang):
    """Keep resources in lang, or without a translation in lang."""
    return [
        r
        for r in resources
        if r.meta.language == lang
        or lang not in (t.meta.language for t in r.translations)
    ]


@jinja_filter
def tagged(resources, tag):
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
def tag_tree(tags):
    """Group tags as (tag, subtags) pairs. Subtags follow their parent."""
    result = []
    for tag in tags:
        if result and tag.startswith(result[-1][0] + "-"):
            result[-1][1].append(tag)
        else:
            result.append((tag, []))
    return result


@jinja_filter
def ai_usage_emoji(entry, emojis):
    """Get the emoji for the key matching the start of an AI usage entry."""
    emojis = dict(emojis or {})
    for key, emoji in emojis.items():
        if key != "default" and entry.startswith(key):
            return emoji
    return emojis.get("default")


class ReadingTime(int):
    """Reading time in minutes, with word count accessible via .words."""

    def __new__(cls, minutes, words):
        obj = super().__new__(cls, minutes)
        obj.words = words
        return obj


@jinja_filter
def reading_time(html, words_per_minute=200, code_lines_per_minute=30):
    """Compute reading time in minutes from HTML."""
    d = pq(html, parser="html")
    code_blocks = d.find("pre")
    code_lines = sum(
        sum(1 for line in el.text_content().splitlines() if line.strip())
        for el in code_blocks
    )
    code_blocks.remove()
    d.find(".footnote").remove()
    words = len(d.text().split())
    minutes = round(words / words_per_minute + code_lines / code_lines_per_minute)
    return ReadingTime(max(1, minutes), words)


@jinja_filter
def clean_rss(html):
    doc = pq(html)
    doc(".when-js").remove()
    doc(".when-nojs").remove()
    doc("a").filter(lambda i, el: pq(el).text() == "#").remove()
    doc(".footnote-backref").text("↩")
    # Markup so the XHTML markup is inserted into the atom feed as
    # structure rather than autoescaped to entity-encoded text.
    return Markup(doc.html())

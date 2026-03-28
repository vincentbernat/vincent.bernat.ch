import os
import jinja2
import re
from babel.dates import format_date
from distutils.version import LooseVersion
from pyquery import PyQuery as pq


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
                formatted = f"{mo.group("before")}{replacement}{mo.group("after")}"
    return formatted


def same_tag(resource, attribute, skip=0):
    """Returns the next resource with at least a common tag using the
    provided attribute to iterate over resources.
    """
    tags = {
        t.name
        for t in getattr(resource, "tags", [])
        if t.name != "outdated" and t.name != "unclassified"
    }
    candidate = resource
    while candidate:
        candidate = getattr(candidate, attribute, None)
        if skip:
            skip -= 1
            continue
        ctags = {t.name for t in getattr(candidate, "tags", [])}
        if "outdated" in ctags:
            continue
        if len(tags & ctags) > 0:
            break
    return candidate


def media_listing(resources, directory):
    """Version-sort media resources contained in directory."""
    resources = [
        r
        for r in resources
        if r.source_file.parent.path.endswith("/media/" + directory)
    ]
    to_sort = [
        {"resource": r, "version": LooseVersion(r.relative_path)} for r in resources
    ]
    to_sort.sort(key=lambda x: x["version"])
    return [r["resource"] for r in to_sort]


def mastodon_href(handle):
    """Turn a mastodon handle into an href (very naive)."""
    mo = re.match(r"@(.*)@(.*)", handle)
    assert mo
    return f"https://{mo.group(2)}/@{mo.group(1)}"


@jinja2.contextfunction
def include_file(ctx, name):
    target = os.path.join(str(ctx.parent["node"]), name)
    with open(target, "r") as f:
        return jinja2.Markup(f.read())


class ReadingTime(int):
    """Reading time in minutes, with word count accessible via .words."""

    def __new__(cls, minutes, words):
        obj = super().__new__(cls, minutes)
        obj.words = words
        return obj


def reading_time(html, words_per_minute=200, code_lines_per_minute=30):
    """Compute reading time in minutes from HTML."""
    d = pq(html, parser="html")
    code_blocks = d.find("pre")
    code_lines = sum(
        sum(1 for line in el.text_content().splitlines() if line.strip())
        for el in code_blocks
    )
    code_blocks.remove()
    d.find(".footnote, .endnote").remove()
    words = len(d.text().split())
    minutes = round(words / words_per_minute + code_lines / code_lines_per_minute)
    return ReadingTime(max(1, minutes), words)


@jinja2.contextfilter
def clean_rss(ctx, html):
    doc = pq(html)
    doc(".when-js").remove()
    doc(".when-nojs").remove()
    doc("a").filter(lambda i, el: pq(el).text() == "#").remove()
    return doc.html()

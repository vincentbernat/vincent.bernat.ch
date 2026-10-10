import os
import jinja2
import re
import tomllib
from markupsafe import Markup
from markdown import Markdown
from babel.dates import format_date
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


@jinja2.pass_context
def markdown(ctx, value):
    """Convert markdown to HTML, giving the extensions access to the resource."""
    config = ctx.environment.config.markdown
    extension_configs = config.extension_configs.to_dict()
    extension_configs["extensions.markdown.shortlinks"] = {
        "l10n": getattr(ctx["resource"].meta, "l10n", None)
    }
    return Markdown(
        extensions=config.extensions,
        extension_configs=extension_configs,
        output_format=config.output_format,
    ).convert(value)


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


NATURAL_RE = re.compile(r"(\d+)")


def natural_key(value):
    """Sort key comparing digit runs as numbers."""
    return [
        int(part) if index % 2 else part
        for index, part in enumerate(NATURAL_RE.split(value))
    ]


def media_listing(resources, directory):
    """Version-sort media resources contained in directory."""
    resources = [
        r
        for r in resources
        if r.source_file.parent.path.endswith("/media/" + directory)
    ]
    return sorted(resources, key=lambda r: natural_key(r.relative_path))


def mastodon_href(handle):
    """Turn a mastodon handle into an href (very naive)."""
    mo = re.match(r"@(.*)@(.*)", handle)
    assert mo
    return f"https://{mo.group(2)}/@{mo.group(1)}"


@jinja2.pass_context
def include_file(ctx, name):
    target = os.path.join(str(ctx.parent["node"]), name)
    with open(target) as f:
        return Markup(f.read())


def as_list(value):
    """Wrap a single string into a list."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return value


@jinja2.pass_context
def licenses(ctx, lang):
    """List REUSE.toml annotations as (paths, items), items being Markdown."""
    target = os.path.join(str(ctx["site"].sitepath), "REUSE.toml")
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


def in_language(resources, lang):
    """Keep resources in lang, or without a translation in lang."""
    return [
        r
        for r in resources
        if r.meta.language == lang
        or lang not in (t.meta.language for t in r.translations)
    ]


def tagged(resources, tag):
    """Keep resources with tag or one of its subtags. Resources only tagged
    as outdated are part of the unclassified tag."""
    tag = str(tag)
    result = []
    for r in resources:
        tags = [str(t) for t in getattr(r.meta, "tags", None) or []]
        if any(t == tag or t.startswith(tag + "-") for t in tags) or (
            tag == "unclassified" and tags == ["outdated"]
        ):
            result.append(r)
    return result


def tag_tree(tags):
    """Group tags as (tag, subtags) pairs. Subtags follow their parent."""
    result = []
    for tag in tags:
        if result and tag.startswith(result[-1][0] + "-"):
            result[-1][1].append(tag)
        else:
            result.append((tag, []))
    return result


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


@jinja2.pass_context
def clean_rss(ctx, html):
    doc = pq(html)
    doc(".when-js").remove()
    doc(".when-nojs").remove()
    doc("a").filter(lambda i, el: pq(el).text() == "#").remove()
    doc(".footnote-backref").text("↩")
    # Markup so the XHTML markup is inserted into the atom feed as
    # structure rather than autoescaped to entity-encoded text.
    return Markup(doc.html())

"""Synchronize Miniflux feeds with a YAML file."""

import json
import os
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from ..model.blogroll import FEEDS, Feed, load
from . import Exit, command

# Width of lines
WIDTH = 64


class IndentedDumper(yaml.SafeDumper):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Lines go over the width until the next space
        if kwargs.get("width") is None:
            kwargs["width"] = WIDTH
        super().__init__(*args, **kwargs)

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        return super().increase_indent(flow, False)

    def represent_dict(self, data: Any) -> yaml.MappingNode:
        # Descriptions not fitting after the key in folded style
        node = super().represent_dict(data)
        for key, value in node.value:
            if (
                key.value == "description"
                and len(value.value) > WIDTH - len("    description: ")
                and "\n" not in value.value
            ):
                value.style = ">"
        return node


IndentedDumper.add_representer(dict, IndentedDumper.represent_dict)


def miniflux(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    url = os.environ.get("MINIFLUX_URL", "https://reader.miniflux.app").rstrip("/")
    request = urllib.request.Request(
        f"{url}/v1/{path}",
        method=method,
        data=json.dumps(body).encode() if body else None,
        headers={
            "X-Auth-Token": os.environ["MINIFLUX_API_KEY"],
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request) as response:
        content = response.read()
        return content and json.loads(content)


@command("miniflux-pull")
def pull(file: str = str(FEEDS), dry_run: bool = False) -> None:
    """Pull Miniflux feeds to a YAML file."""
    feeds = miniflux("GET", "feeds")
    previous = {
        e.feed: (category, e)
        for category, entries in load(file).items()
        for e in entries
    }
    result: dict[str, list[dict[str, Any]]] = {}
    for feed in sorted(
        feeds,
        key=lambda f: (f["category"]["title"].lower(), f["title"].lower()),
    ):
        entry = Feed(
            title=feed["title"],
            url=feed["site_url"],
            feed=feed["feed_url"],
            description=feed.get("description") or "",
        )
        category = feed["category"]["title"]
        if entry.feed not in previous:
            print(f"add feed {entry.feed}")
        else:
            old_category, old = previous.pop(entry.feed)
            changes = [
                k
                for k in ("title", "url", "description")
                if getattr(old, k) != getattr(entry, k)
            ]
            if old_category != category:
                changes.append("category")
            if changes:
                print(f"update feed {entry.feed}: {', '.join(changes)}")
            entry = replace(
                entry,
                starred=old.starred,
                hidden=old.hidden,
                language=old.language,
                note=old.note,
                articles=old.articles,
            )
        result.setdefault(category, []).append(entry.dump())
    for url in previous:
        print(f"delete feed {url}")
    output = yaml.dump(
        result,
        Dumper=IndentedDumper,
        sort_keys=False,
        allow_unicode=True,
        explicit_start=True,
    )
    if dry_run:
        print(output, end="")
    else:
        Path(file).write_text(output, encoding="utf-8")


@command("miniflux-push")
def push(file: str = str(FEEDS), dry_run: bool = False) -> None:
    """Push feeds from a YAML file to Miniflux."""
    local = load(file)
    if not local:
        raise Exit(f"{file} is missing or empty")
    feeds = {f["feed_url"]: f for f in miniflux("GET", "feeds")}
    categories = {c["title"]: c["id"] for c in miniflux("GET", "categories")}
    for category, entries in local.items():
        if category not in categories:
            print(f"create category {category}")
            categories[category] = (
                None
                if dry_run
                else miniflux("POST", "categories", {"title": category})["id"]
            )
        for entry in entries:
            feed = feeds.get(entry.feed)
            if feed is None:
                print(f"create feed {entry.feed}")
                if dry_run:
                    continue
                feed = {
                    "id": miniflux(
                        "POST",
                        "feeds",
                        {
                            "feed_url": entry.feed,
                            "category_id": categories[category],
                        },
                    )["feed_id"]
                }
            current = {
                "title": feed.get("title"),
                "site_url": feed.get("site_url"),
                "description": feed.get("description") or "",
                "category_id": feed.get("category", {}).get("id"),
            }
            wanted = {
                "title": entry.title,
                "site_url": entry.url,
                "description": entry.description,
                "category_id": categories[category],
            }
            changes = {k: v for k, v in wanted.items() if current[k] != v}
            if changes:
                print(f"update feed {entry.feed}: {', '.join(changes)}")
                if not dry_run:
                    miniflux("PUT", f"feeds/{feed['id']}", changes)
    kept = {e.feed for entries in local.values() for e in entries}
    for url, feed in feeds.items():
        if url not in kept:
            print(f"delete feed {url}")
            if not dry_run:
                miniflux("DELETE", f"feeds/{feed['id']}")

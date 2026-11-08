"""Blogroll, from feeds.yaml."""

import locale
import random
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import xxhash
import yaml

from .. import config

FEEDS = config.ROOT / "feeds.yaml"
# Share of picks among feeds in the categories of an article
MATCHING_SHARE = 3 / 4
# How much more often starred feeds are picked
STARRED_WEIGHT = 2


@dataclass(frozen=True)
class FeedArticle:
    """One article of a feed to highlight."""

    url: str
    title: str


@dataclass(frozen=True)
class Feed:
    """One feed in feeds.yaml."""

    title: str  # Title (preferably the name of the author)
    url: str  # URL of the site
    feed: str  # URL of the feed
    description: str = ""  # Description of the blog
    language: Literal["fr", "en"] | None = None  # Language of the blog (local)
    starred: bool = False  # One of my favorites (local)
    hidden: bool = False  # Do not publish (local)
    # Articles to highlight (local)
    articles: list[FeedArticle] = field(default_factory=list)
    note: str = ""  # Free-form note, "#" in feeds.yaml (local)

    def __post_init__(self) -> None:
        if self.language not in (None, "fr", "en"):
            raise ValueError(f"{self.feed}: unknown language {self.language}")

    @property
    def summary(self) -> str:
        """First sentence of the description, without the final dot."""
        return re.split(r"\.(?:\s|$)", self.description, maxsplit=1)[0]

    def dump(self) -> dict[str, Any]:
        """Feed as a mapping, without the optional fields left empty."""
        return {
            ("#" if k == "note" else k): v
            for k, v in asdict(self).items()
            if v or k in ("title", "url", "feed")
        }


def load(file: str) -> dict[str, list[Feed]]:
    path = Path(file)
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    result = {}
    for category, entries in data.items():
        feeds = []
        for entry in entries:
            entry = {("note" if k == "#" else k): v for k, v in entry.items()}
            entry["articles"] = [FeedArticle(**a) for a in entry.get("articles", [])]
            feeds.append(Feed(**entry))
        result[category] = feeds
    return result


def tag_index(category: str) -> int | None:
    """Index of the tag matching a category, by name or description."""
    for index, (tag, info) in enumerate(config.TAGS.items()):
        names = {tag, *(str(v).lower() for k, v in info.items() if "descr" in k)}
        if category.lower() in names:
            return index
    return None


def rank(category: str) -> tuple[int, int, str]:
    """Sort key for categories: Computing first, then categories matching a
    tag in the order of tags, then the others, and Misc last."""
    if category == "Computing":
        return (0, 0, "")
    if category == "Misc":
        return (3, 0, "")
    index = tag_index(category)
    if index is not None:
        return (1, index, "")
    return (2, 0, category.lower())


def title_key(feed: Feed) -> str:
    """Sort key for titles: case insensitive, with the collation of the locale
    set by published()."""
    return locale.strxfrm(feed.title.casefold())


def favorites(categories: Iterable[tuple[str, list[Feed]]]) -> list[Feed]:
    """Starred feeds of published categories, sorted by title."""
    starred = [f for _, feeds in categories for f in feeds if f.starred]
    return sorted(starred, key=title_key)


def published(file: str = str(FEEDS)) -> list[tuple[str, list[Feed]]]:
    """Feeds to publish, by category, starred ones first."""
    locale.setlocale(locale.LC_COLLATE, "en_US.UTF-8")
    result = []
    for category, feeds in sorted(load(file).items(), key=lambda c: rank(c[0])):
        shown = [f for f in feeds if not f.hidden]
        if shown:
            shown.sort(key=lambda f: (not f.starred, title_key(f)))
            result.append((category, shown))
    return result


def related(
    tags: Iterable[str], language: str, seed: str, file: str = str(FEEDS)
) -> tuple[Feed, FeedArticle | None] | None:
    """A feed in a language, and one of its articles if any, picked at random
    with the same seed and file for the same result. When some feeds are in the
    categories of the tags, pick one of them with a MATCHING_SHARE probability,
    and one in Computing otherwise. Feeds in other categories are never
    picked. Starred feeds weigh STARRED_WEIGHT."""
    names = list(config.TAGS)
    general = {tag.partition("-")[0] for tag in tags}
    matching: list[Feed] = []
    computing: list[Feed] = []
    for category, shown in published(file):
        index = tag_index(category)
        if index is not None and names[index] in general:
            pool = matching
        elif category == "Computing":
            pool = computing
        else:
            continue
        pool.extend(f for f in shown if f.language in (None, language))
    digest = xxhash.xxh3_128_hexdigest(Path(file).read_bytes())
    rng = random.Random(f"{seed}:{digest}")
    if matching and (not computing or rng.random() < MATCHING_SHARE):
        pool = matching
    elif computing:
        pool = computing
    else:
        return None
    feed = rng.choices(pool, [STARRED_WEIGHT if f.starred else 1 for f in pool])[0]
    return feed, rng.choice(feed.articles) if feed.articles else None

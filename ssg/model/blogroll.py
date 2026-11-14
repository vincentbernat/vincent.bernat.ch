"""Blogroll, from feeds.yaml."""

import functools
import locale
import re
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import xxhash
import yaml

from .. import config

FEEDS = config.ROOT / "feeds.yaml"
# Number of posts exchanging their feeds to match their tags
GROUP = 8
PHI = (5**0.5 - 1) / 2
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


@functools.cache
def line(file: str, digest: str, language: str) -> list[tuple[str | None, Feed]]:
    """Feeds in a language which can be picked for a post, each with the tag of
    its category, None for Computing.

    """
    names = list(config.TAGS)
    result = []
    for category, shown in published(file):
        index = tag_index(category)
        if index is None and category != "Computing":
            # Only a valid category is allowed, or computing
            continue
        tag = None if index is None else names[index]
        for feed in shown:
            # Exclude myself
            if feed.url.startswith(config.BASE):
                continue
            # Feeds in English are picked for all languages
            if feed.language in (None, "en", language):
                # Starred feeds are weighted more
                result.extend([(tag, feed)] * (STARRED_WEIGHT if feed.starred else 1))
    result.sort(
        key=lambda item: xxhash.xxh3_64_intdigest(f"{digest}:{item[1].feed}".encode())
    )
    return result


def assign(scores: list[list[int]]) -> list[int]:
    """Slot of each post for the highest total score, with scores[post][slot]."""
    size = len(scores)
    best: dict[int, tuple[int, list[int]]] = {0: (0, [])}
    for mask in range(1, 1 << size):
        post = mask.bit_count() - 1
        best[mask] = max(
            (
                best[mask ^ (1 << slot)][0] + scores[post][slot],
                best[mask ^ (1 << slot)][1] + [slot],
            )
            for slot in range(size)
            if mask >> slot & 1
        )
    return best[(1 << size) - 1][1]


def related(
    rank: int,
    group: Sequence[Iterable[str]],
    language: str,
    seed: str,
    file: str = str(FEEDS),
) -> tuple[Feed, FeedArticle | None] | None:
    """A feed for a post in a language, and one of its articles if any."""
    digest = xxhash.xxh3_128_hexdigest(Path(file).read_bytes())
    feeds = line(file, digest, language)
    if not feeds:
        return None

    # The rank is the number of newer posts. Posts are grouped by GROUP ranks.
    first = rank - rank % GROUP

    # Each rank gets a feed, with all feeds used as often as the others
    slots = [feeds[int((first + i) * PHI % 1 * len(feeds))] for i in range(len(group))]

    # Posts of a group exchange their feeds to match their tags, or to get one
    # in Computing otherwise
    scores = []
    for tags in group:
        general = {tag.partition("-")[0] for tag in tags}
        scores.append(
            [2 if tag in general else 1 if tag is None else 0 for tag, _ in slots]
        )
    _, feed = slots[assign(scores)[rank - first]]
    article = min(
        feed.articles,
        key=lambda a: xxhash.xxh3_64_intdigest(f"{digest}:{seed}:{a.url}".encode()),
        default=None,
    )
    return feed, article

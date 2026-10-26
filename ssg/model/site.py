"""The site: all nodes and resources, and URLs."""

import fnmatch
import functools
import itertools
import json
import posixpath
import subprocess
import urllib.parse
from datetime import UTC, datetime
from operator import attrgetter
from pathlib import Path
from typing import Any

import yaml

from .. import config, deps
from ..tools import write
from .meta import FRONTMATTER, Meta
from .node import CIRCULAR, SORTERS, Node
from .resource import PYTHON, Resource

NODEMETA = "meta.yaml"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", newline="")


def encode_url(base: str, path: str) -> str:
    path = urllib.parse.quote(path.strip(), "/@")
    return base.strip().rstrip("/") + "/" + path.lstrip("/")


class Site:
    def __init__(self, mode: config.Mode) -> None:
        self.mode = mode
        self.nodes: dict[str, Node] = {}
        self.resources: dict[str, Resource] = {}
        # Generated media files: path relative to media to file
        self.generated: dict[str, Path] = {}
        self.load()

    # Templates use these names
    @property
    def content(self) -> Node:
        return self.nodes[""]

    def resource(self, path: str) -> Resource | None:
        resource = self.resources.get(path)
        deps.record(f"r:{path}", resource.digest if resource else "")
        return resource

    def node(self, path: str) -> Node | None:
        return self.nodes.get(path)

    def sorted(self, name: str) -> list[Resource]:
        return self.content.sorted(name)

    def tracks(self, video: str) -> list[Resource]:
        """Chapters and subtitles of a video."""
        deps.record(f"v:{video}", ",".join(r.name for r in self._tracks(video)))
        return self._tracks(video)

    def _tracks(self, video: str) -> list[Resource]:
        return [
            r
            for r in self.nodes["media/videos"]._sorted("name")
            if r.name.endswith(".vtt") and r.name.startswith(f"{video}.")
        ]

    @functools.cached_property
    def tags(self) -> dict[str, Meta]:
        return {name: Meta(value) for name, value in config.TAGS.items()}

    def content_url(self, path: str) -> str:
        url = encode_url("/", path)
        parent, name = posixpath.split(url.rstrip("/"))
        if name == "index.html":
            url = parent.rstrip("/")
        elif name.endswith(".html"):
            url = posixpath.join(parent, name[:-5])
        return url or "/"

    def media_url(self, path: str) -> str:
        for prefix, url in self.mode.cdn:
            if path.startswith(prefix):
                return encode_url(url, path[len(prefix) :])
        return encode_url(self.mode.media_url, path)

    def output(self, path: str) -> Path:
        """Path in the output directory."""
        return self.mode.output / path

    def raw(self, path: str) -> Path:
        """File for a media path, before fingerprinting it."""
        if path in self.generated:
            return self.generated[path]
        return config.CONTENT / "media" / path

    def manifest(self, path: str) -> Path:
        """Information about a fingerprinted media file."""
        return self.mode.cache / "fingerprints" / (path + ".json")

    def fingerprint(self, path: str) -> dict[str, Any] | None:
        """Hashed name and integrity of a fingerprinted media file."""
        manifest = self.manifest(path)
        deps.record_file(manifest)
        try:
            return json.loads(manifest.read_text())
        except FileNotFoundError:
            return None

    def hashed(self, path: str) -> str:
        """Name of a media file with a hash of its content."""
        raw = self.raw(path)
        deps.record_file(raw)
        try:
            digest = deps.cached_file_hash(str(raw), deps.file_digest(raw))
        except FileNotFoundError:
            raise ValueError(f"unknown media file {path}") from None
        root, ext = posixpath.splitext(path)
        return f"{root}.{digest[:14]}{ext}"

    def load(self) -> None:
        root = Node(self, "", None)
        self.nodes[""] = root
        for directory, dirnames, filenames in config.CONTENT.walk(follow_symlinks=True):
            dirnames[:] = sorted(d for d in dirnames if not ignored(d))
            relative = directory.relative_to(config.CONTENT).as_posix()
            relative = "" if relative == "." else relative
            node = self.nodes[relative]
            for name in sorted(dirnames):
                path = posixpath.join(relative, name)
                child = Node(self, path, node)
                node.children.append(child)
                self.nodes[path] = child
            for name in sorted(filenames):
                if ignored(name):
                    continue
                path = posixpath.join(relative, name)
                resource = Resource(self, node, path)
                node.resources.append(resource)
                self.resources[path] = resource
        self.load_feeds()
        self.load_meta()
        self.load_dates()
        self.load_combine()
        self.load_translations()
        self.load_sorters()
        self.load_tags()

    def load_feeds(self) -> None:
        """Feeds of tags, named atom-<tag>.xml, use the source of atom.xml."""
        for language in config.LANGUAGES:
            feed = self.resources.get(f"{language}/blog/atom.xml")
            if feed is None:
                continue
            for tag, info in config.TAGS.items():
                if not info.get("feed"):
                    continue
                path = posixpath.join(feed.node.path, f"atom-{tag}.xml")
                resource = Resource(self, feed.node, path, feed.source)
                feed.node.resources.append(resource)
                self.resources[path] = resource

    def load_meta(self) -> None:
        for node in self.content.walk():
            parent = node.parent.meta if node.parent else Meta(config.META)
            nodemeta = node.source / NODEMETA
            if nodemeta.is_file():
                node.meta = Meta(
                    yaml.load(read_text(nodemeta), yaml.CSafeLoader), parent
                )
                self.resources[posixpath.join(node.path, NODEMETA)].processable = False
            else:
                node.meta = Meta(None, parent)
            for resource in node.resources:
                data = None
                if resource.text:
                    text = resource.source_text
                    resource.python = text.startswith(PYTHON)
                    match = FRONTMATTER.match(text)
                    if match:
                        data = yaml.load(match.group(1), yaml.CSafeLoader)
                resource.meta = Meta(data, node.meta)

    def load_dates(self) -> None:
        dates = git_dates(self.mode.cache / "git-dates.json")
        for resource in self.resources.values():
            created = resource.meta.get("created")
            modified = resource.meta.get("modified")
            if created != "git" and modified != "git":
                continue
            # Files not committed yet use their modification time
            # Only the day, so saving does not change what other pages show
            mtime = datetime.fromtimestamp(resource.source.stat().st_mtime, UTC)
            mtime = mtime.replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=None
            )
            git_created, git_modified = dates.get(resource.path, (None, None))
            if created == "git":
                resource.meta.created = git_created or mtime
            if modified == "git":
                resource.meta.modified = git_modified or mtime

    def load_combine(self) -> None:
        """A stylesheet or a script named foo.css is followed by the files
        named foo.*.css of the same directory, in name order."""
        for resource in self.resources.values():
            if resource.kind not in ("css", "js"):
                continue
            pattern = f"{resource.stem}.*.{resource.kind}"
            resource.combined = sorted(
                (
                    r
                    for r in resource.node.resources
                    if fnmatch.fnmatch(r.name, pattern)
                ),
                key=attrgetter("name"),
            )
            for r in resource.combined:
                r.processable = False

    def load_translations(self) -> None:
        uuids: dict[str, list[Resource]] = {}
        for resource in self.content.walk_resources():
            if "uuid" in resource.meta and "language" in resource.meta:
                uuids.setdefault(resource.meta.uuid, []).append(resource)
        for resources in uuids.values():
            for resource in resources:
                resource._translations = [
                    r for r in resources if r.meta.language != resource.meta.language
                ]

    def load_sorters(self) -> None:
        for name in SORTERS:
            resources = self.content._sorted(name)
            for prev, next in itertools.pairwise(resources):
                prev.neighbors[f"next_by_{name}"] = next
                next.neighbors[f"prev_by_{name}"] = prev
            if name in CIRCULAR and resources:
                resources[0].neighbors[f"prev_by_{name}"] = resources[-1]
                resources[-1].neighbors[f"next_by_{name}"] = resources[0]

    def load_tags(self) -> None:
        for resource in self.content._sorted("time"):
            resource.tags.extend(resource.meta.get("tags") or [])


def ignored(name: str) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in config.IGNORE)


def git_dates(cache: Path) -> dict[str, tuple[datetime, datetime]]:
    """Map paths relative to content to their creation and modification
    dates from git. The result is kept in a cache file until HEAD changes."""
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=config.ROOT, text=True
    ).strip()
    try:
        cached = json.loads(cache.read_text())
    except FileNotFoundError, json.JSONDecodeError:
        cached = {}
    if cached.get("head") == head:
        dates = cached["dates"]
    else:
        dates = git_timestamps()
        write(cache, json.dumps({"head": head, "dates": dates}))

    def utc(ts: int) -> datetime:
        return datetime.fromtimestamp(ts, UTC).replace(tzinfo=None)

    return {path: (utc(c), utc(m)) for path, (c, m) in dates.items()}


def git_timestamps() -> dict[str, list[int]]:
    """Map paths relative to content to their creation and modification
    timestamps from git."""
    output = subprocess.check_output(
        [
            "git",
            "log",
            "--format=%at",
            "--name-status",
            "--no-merges",
            "--diff-filter=AMR",
            "--reverse",
            str(config.CONTENT),
        ],
        cwd=config.ROOT,
        text=True,
    )
    dates = {}
    current = None
    prefix = config.CONTENT.relative_to(config.ROOT).as_posix() + "/"
    for line in output.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.isdigit():
            current = int(line)
            continue
        if current is None:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        path = parts[2] if parts[0].startswith("R") else parts[1]
        path = path.removeprefix(prefix)
        if path not in dates:
            dates[path] = [current, current]
        else:
            dates[path][1] = current
    return dates

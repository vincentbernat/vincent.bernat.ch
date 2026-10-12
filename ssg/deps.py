"""Record what a task reads, to know later if it should run again.

Templates read data from other resources (titles of the next articles, list
of articles for an index, ...). While a task runs, each read is recorded as a
key and a digest of the value. The task is up-to-date as long as each key
still gives the same digest.

"""

from __future__ import annotations

import functools
import hashlib
import os
import shutil
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

import xxhash
from doit.dependency import FileChangedChecker

if TYPE_CHECKING:
    from .model.resource import Resource
    from .model.site import Site

recorder: Recorder | None = None
# Files of the build code, set when planning
code_files: Sequence[str] = ()


class Recorder:
    """Record the reads made inside a "with" block."""

    def __init__(self) -> None:
        self.items: dict[str, str] = {}
        self.previous: Recorder | None = None

    def __enter__(self) -> Self:
        global recorder
        self.previous = recorder
        recorder = self
        return self

    def __exit__(self, *args: object) -> None:
        global recorder
        recorder = self.previous


def recorded(function: Callable[..., object], *args: Any) -> object:
    """Run a task action. Add what it read to its values, for uptodate()."""
    with Recorder() as r:
        result = function(*args)
    if result is None or result is True:
        return {"deps": r.items}
    if isinstance(result, dict):
        return result | {"deps": r.items}
    return result


def cache[R](function: Callable[..., R]) -> Callable[..., R]:
    """Like functools.cache, but each call records what the first call
    recorded."""

    @functools.cache
    def first(*args: Any) -> tuple[R, dict[str, str]]:
        with Recorder() as r:
            return function(*args), r.items

    @functools.wraps(function)
    def call(*args: Any) -> R:
        result, items = first(*args)
        if recorder is not None:
            recorder.items.update(items)
        return result

    return call


def record(key: str, digest: str) -> None:
    if recorder is not None:
        recorder.items[key] = digest


def record_resource(resource: Resource | None) -> None:
    if recorder is not None and resource is not None:
        recorder.items[f"r:{resource.path}"] = resource.digest


def record_content(resource: Resource) -> None:
    """Record the source used by a task. If it changes while the task runs,
    doit records the new source as already built."""
    if recorder is not None:
        recorder.items[f"c:{resource.path}"] = content_digest(resource)


def content_digest(resource: Resource) -> str:
    return xxhash.xxh3_128_hexdigest(resource.source_text.encode("utf-8"))


@functools.cache
def code_digest() -> str:
    """Digest of the build code."""
    hasher = xxhash.xxh3_128()
    for path in code_files:
        hasher.update(f"{path}\0{file_hash(path)}\n".encode())
    return hasher.hexdigest()


def record_code() -> None:
    """Record the build code used by a task."""
    record("k:", code_digest())


@functools.cache
def tool_path(name: str) -> str:
    """Path of a tool. With Nix, a new version has a new path."""
    return str(Path(shutil.which(name) or name).resolve())


def tool(name: str) -> None:
    """Record a tool used by a task."""
    record(f"t:{name}", tool_path(name))


def getenv(name: str, default: str | None = None) -> str:
    """Record an environment variable used by a task and return its value."""
    value = os.environ.get(name, default)
    if value is None:
        raise KeyError(f"missing environment variable {name}")
    record(f"e:{name}", value)
    return value


def record_file(path: str | os.PathLike[str]) -> None:
    if recorder is not None:
        path = str(path)
        recorder.items[f"f:{path}"] = file_digest(path)


def file_hash(path: str | os.PathLike[str]) -> str:
    """Digest of the content of a file."""
    with Path(path).open("rb", buffering=0) as f:
        # The xxhash stubs do not match the protocol expected by hashlib
        digest = hashlib.file_digest(f, xxhash.xxh3_128)  # type: ignore[arg-type]
    return digest.hexdigest()


class XXHashChecker(FileChangedChecker):
    """Check if a file_dep changed for doit, like its MD5 checker, but with
    xxh3-128. A file with the same modification time did not change. Otherwise,
    compare the size, then the content."""

    def check_modified(
        self, file_path: str, file_stat: os.stat_result, state: list[Any]
    ) -> bool:
        timestamp, size, digest = state
        if file_stat.st_mtime == timestamp:
            return False
        if file_stat.st_size != size:
            return True
        return bool(digest != file_hash(file_path))

    def get_state(
        self, dep: str, current_state: list[Any] | None
    ) -> tuple[float, int, str] | None:
        st = Path(dep).stat()
        if current_state and current_state[0] == st.st_mtime:
            return None
        return st.st_mtime, st.st_size, file_hash(dep)


def file_digest(path: str | os.PathLike[str]) -> str:
    try:
        st = Path(path).stat()
    except FileNotFoundError:
        return ""
    return f"{st.st_mtime_ns}:{st.st_size}"


# Kinds of recorded keys, as handled by state(). A key is "<kind>:<name>".
KINDS = {
    # resource path → hash of URL, metadata, tags and translations
    "r": "resource",
    # resource path → hash of its text
    "c": "content",
    # file path → modification time and size
    "f": "file",
    # node path and sorter, like "en/blog:time_en" → hash of the sorted resources
    "w": "sorted",
    # resource path and neighbor, like "…:next_by_time_en" → hash of the neighbor
    "n": "neighbor",
    # video name → names of its chapter and subtitle files
    "v": "tracks",
    # empty → hash of content of code files
    "k": "code",
    # tool name → path of the tool
    "t": "tool",
    # variable name → its value
    "e": "environment",
    # empty → current year
    "y": "year",
}


def state(site: Site, key: str) -> str | None:
    """Current digest for a key."""
    kind, _, what = key.partition(":")
    match kind:
        case "r":
            resource = site.resources.get(what)
            return resource.digest if resource else ""
        case "c":
            resource = site.resources.get(what)
            return content_digest(resource) if resource and resource.text else ""
        case "f":
            return file_digest(what)
        case "w":
            name, _, sorter = what.rpartition(":")
            node = site.nodes.get(name)
            return node.sorted_digest(sorter) if node else ""
        case "n":
            path, _, attr = what.rpartition(":")
            resource = site.resources.get(path)
            if resource is None:
                return ""
            other = resource.neighbors.get(attr)
            return other.digest if other else ""
        case "v":
            return ",".join(r.name for r in site._tracks(what))
        case "k":
            return code_digest()
        case "t":
            return tool_path(what)
        case "e":
            return os.environ.get(what, "")
        case "y":
            return str(datetime.now().year)  # noqa: DTZ005
    return None


def uptodate(site: Site) -> Callable[[object, dict[str, Any]], bool]:
    """Build an uptodate callable for doit, using recorded values."""

    def check(task: object, values: dict[str, Any]) -> bool:
        recorded = values.get("deps")
        if recorded is None:
            return False
        return all(state(site, key) == digest for key, digest in recorded.items())

    return check

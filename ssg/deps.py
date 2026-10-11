"""Record what a task reads, to know later if it should run again.

Templates read data from other resources (titles of the next articles, list
of articles for an index, ...). While a task runs, each read is recorded as a
key and a digest of the value. The task is up-to-date as long as each key
still gives the same digest.

"""

import functools
import hashlib
import os
import shutil
from datetime import datetime

recorder = None
# Files of the build code, set when planning
code_files = ()


class Recorder:
    """Record the reads made inside a "with" block."""

    def __init__(self):
        self.items = {}
        self.previous = None

    def __enter__(self):
        global recorder
        self.previous = recorder
        recorder = self
        return self

    def __exit__(self, *args):
        global recorder
        recorder = self.previous


def recorded(function, *args):
    """Run a task action. Add what it read to its values, for uptodate()."""
    with Recorder() as r:
        result = function(*args)
    if result is None or result is True:
        return {"deps": r.items}
    if isinstance(result, dict):
        return result | {"deps": r.items}
    return result


def cache(function):
    """Like functools.cache, but each call records what the first call
    recorded."""

    @functools.cache
    def first(*args):
        with Recorder() as r:
            return function(*args), r.items

    @functools.wraps(function)
    def call(*args):
        result, items = first(*args)
        if recorder is not None:
            recorder.items.update(items)
        return result

    return call


def record(key, digest):
    if recorder is not None:
        recorder.items[key] = digest


def record_resource(resource):
    if recorder is not None and resource is not None:
        recorder.items[f"r:{resource.path}"] = resource.digest


def record_content(resource):
    """Record the source used by a task. If it changes while the task runs,
    doit records the new source as already built."""
    if recorder is not None:
        recorder.items[f"c:{resource.path}"] = content_digest(resource)


def content_digest(resource):
    return hashlib.sha1(resource.content.encode("utf-8")).hexdigest()


@functools.cache
def code_digest():
    """Digest of the build code. Computed once, before workers start."""
    return hashlib.sha1(
        "\n".join(file_digest(path) for path in code_files).encode()
    ).hexdigest()


def record_code():
    """Record the build code used by a task. If it changes while the task
    runs, doit records the new code as already used."""
    record("k:", code_digest())


@functools.cache
def tool_path(name):
    """Path of a tool. With Nix, a new version has a new path."""
    return os.path.realpath(shutil.which(name) or name)


def tool(name):
    """Record a tool used by a task."""
    record(f"t:{name}", tool_path(name))


def getenv(name, default=None):
    """Record an environment variable used by a task and return its value."""
    value = os.environ.get(name, default)
    if value is None:
        raise KeyError(f"missing environment variable {name}")
    record(f"e:{name}", value)
    return value


def record_file(path):
    if recorder is not None:
        path = str(path)
        recorder.items[f"f:{path}"] = file_digest(path)


def file_digest(path):
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return ""
    return f"{st.st_mtime_ns}:{st.st_size}"


def state(site, key):
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
            node, _, sorter = what.rpartition(":")
            node = site.nodes.get(node)
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
            return str(datetime.now().year)
    return None


def uptodate(site):
    """Build an uptodate callable for doit, using recorded values."""

    def check(task, values):
        recorded = values.get("deps")
        if recorded is None:
            return False
        return all(state(site, key) == digest for key, digest in recorded.items())

    return check

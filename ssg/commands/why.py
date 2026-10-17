"""Show why build tasks would run again."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from doit import get_var
from doit.dependency import Dependency, SqliteDB
from doit.loader import generate_tasks

from .. import config, deps
from . import Exit, command


def relative(path: str) -> str:
    if Path(path).is_relative_to(config.ROOT):
        return str(Path(path).relative_to(config.ROOT))
    return path


@command()
def why(tasks: list[str]) -> None:
    """Show build tasks dependencies."""
    if not tasks:
        raise Exit("no task given, for example page:en/index.html")
    from ..model.site import Site
    from ..tasks.builder import Builder, Environment

    mode = config.MODES["production" if get_var("mode") == "prod" else "development"]
    path = mode.cache / "doit.db"
    if not path.exists():
        raise Exit(f"no {path}, build first")
    site = Site(mode)
    builder = Builder(site)
    planned = {t.name: t for t in generate_tasks("site", builder.tasks())}
    manager = Dependency(SqliteDB, str(path), checker_cls=deps.XXHashChecker)
    for name in tasks:
        task = planned.get(name)
        if task is None:
            raise Exit(f"unknown task {name}")
        status = manager.get_status(task, planned, get_log=True)
        found = status.reasons
        values = manager.get_values(name)
        print(f"{name}: {status.status}")
        for line in reasons(status, values, builder.uptodate):
            print(f"  {line}")

        changed = set(found.get("changed_file_dep", []))
        changed |= set(found.get("added_file_dep", []))
        changed |= set(found.get("missing_file_dep", []))
        section(
            "file_dep", [(d in changed, relative(d)) for d in sorted(task.file_dep)]
        )
        missing = set(found.get("missing_target", []))
        section("targets", [(t in missing, relative(t)) for t in task.targets])

        environment: dict[str, str] = {}
        for utd, _, _ in task.uptodate:
            if isinstance(utd, Environment):
                environment |= utd.config
        previous = values.get("_config") or {}
        section(
            "environment",
            [
                (k in previous and previous[k] != v, f"{k} = {v}")
                for k, v in sorted(environment.items())
            ],
        )

        lines = []
        for key, digest in sorted((values.get("deps") or {}).items()):
            kind, _, what = key.partition(":")
            if kind == "f":
                what = relative(what)
            line = f"{deps.KINDS.get(kind, kind):11} {what} = {digest}"
            lines.append((not deps.unchanged(site, key, digest), line))
        section("recorded", lines)


def section(title: str, lines: list[tuple[bool, str]]) -> None:
    """Display a list of dependencies, with "*" for the changed ones."""
    if not lines:
        return
    print(f"  {title}:")
    for changed, line in lines:
        print(f"  {'*' if changed else ' '} {line}")


def reasons(status: Any, values: dict[str, Any], recorded: object) -> Iterator[str]:
    """Reasons given by doit for a task to run again, when not displayed in a
    section."""
    from ..tasks.builder import Environment

    found = status.reasons
    if status.error_reason:
        yield f"error: {status.error_reason}"
    if found.get("has_no_dependencies"):
        yield "no dependencies, always run"
    for utd, _, _ in found.get("uptodate_false", []):
        if utd is recorded:
            continue
        if isinstance(utd, Environment):
            if "_config" not in values:
                yield "environment changed (previous one unknown)"
            continue
        yield f"uptodate check false: {getattr(utd, '__name__', utd)}"
    if found.get("checker_changed"):
        before, after = found["checker_changed"]
        yield f"file_dep checker changed from {before} to {after}"
    for item in found.get("removed_file_dep", []):
        yield f"removed file_dep: {relative(item)}"

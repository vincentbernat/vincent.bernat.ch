"""Show what build tasks recorded while running, and what changed since."""

import contextlib
import json
import sqlite3
from pathlib import Path

from doit import get_var

from .. import config, deps
from . import Exit, command


@command()
def why(tasks: list[str]) -> None:
    """Show the dependencies recorded by build tasks. Changed ones are marked
    with "*". Use mode=prod for the production build."""
    if not tasks:
        raise Exit("no task given, for example page:en/index.html")
    mode = config.MODES["production" if get_var("mode") == "prod" else "development"]
    path = mode.cache / "doit.db"
    try:
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.OperationalError as e:
        raise Exit(f"cannot open {path}: {e}") from None
    site = None
    with contextlib.closing(db):
        for name in tasks:
            row = db.execute(
                "SELECT task_data FROM doit WHERE task_id = ?", (name,)
            ).fetchone()
            if row is None:
                raise Exit(f"unknown task {name}")
            recorded = json.loads(row[0]).get("_values_:", {}).get("deps")
            if recorded is None:
                print(f"{name}: nothing recorded")
                continue
            if site is None:
                from ..model.site import Site
                from ..tasks.builder import CODE

                deps.code_files = CODE
                site = Site(mode)
            print(f"{name}:")
            for key, digest in sorted(recorded.items()):
                kind, _, what = key.partition(":")
                if kind == "f" and Path(what).is_relative_to(config.ROOT):
                    what = str(Path(what).relative_to(config.ROOT))
                mark = " " if deps.state(site, key) == digest else "*"
                print(f"{mark} {deps.KINDS.get(kind, kind):11} {what} = {digest}")

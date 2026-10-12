"""Copy files, remove obsolete ones."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .builder import Builder


def symlink(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    target.symlink_to(source)


def is_symlink(source: Path, target: Path) -> bool:
    try:
        return target.readlink() == source
    except OSError:
        return False


def copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    source.copy(target)


def prune(builder: Builder) -> None:
    """Remove files from the output directory not produced by this build."""
    out = builder.out
    expected = builder.expected()
    kept = {out / ".git", out / "media" / "pagefind"}
    directories = []
    for directory, dirnames, filenames in out.walk():
        dirnames[:] = [d for d in dirnames if directory / d not in kept]
        directories.append(directory)
        for name in filenames:
            path = directory / name
            if path not in expected:
                print(f"remove {path.relative_to(out)}", file=sys.stderr)
                path.unlink()
    for directory in reversed(directories[1:]):
        if not any(directory.iterdir()):
            directory.rmdir()

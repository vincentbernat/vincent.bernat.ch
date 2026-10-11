"""Helpers shared by the build and the commands."""

import os
import subprocess
from collections.abc import Mapping
from typing import Literal, overload

from . import deps


@overload
def run(
    *args: str | os.PathLike[str],
    input: str | None = None,
    env: Mapping[str, str] | None = None,
    text: Literal[True] = True,
    record: bool = True,
) -> str: ...


@overload
def run(
    *args: str | os.PathLike[str],
    input: bytes | None = None,
    env: Mapping[str, str] | None = None,
    text: Literal[False],
    record: bool = True,
) -> bytes: ...


def run(
    *args: str | os.PathLike[str],
    input: str | bytes | None = None,
    env: Mapping[str, str] | None = None,
    text: bool = True,
    record: bool = True,
) -> str | bytes:
    """Run a command and return its output. When it fails, the error includes
    what it printed. The task using it depends on the tool, unless record is
    false."""
    if record:
        deps.tool(str(args[0]))
    result = subprocess.run(  # type: ignore[call-overload]
        [str(a) for a in args],
        input=input,
        env=env,
        capture_output=True,
        check=False,
        text=text,
        **({"errors": "replace"} if text else {}),
    )
    if result.returncode != 0:
        stdout, stderr = result.stdout, result.stderr
        if not text:
            stdout = stdout.decode("utf-8", "replace")
            stderr = stderr.decode("utf-8", "replace")
        raise RuntimeError(f"{args[0]} failed:\n{stdout}{stderr}")
    return result.stdout


def human(size: float) -> str:
    """Size in bytes, for humans."""
    if size < 1024:
        return f"{size} B"
    for unit in ("KiB", "MiB"):
        size /= 1024
        if size < 1024:
            return f"{size:.1f} {unit}"
    return f"{size / 1024:.1f} GiB"


def write(path: str | os.PathLike[str], content: str | bytes) -> None:
    """Write a file, unless it already has this content. Files reading it are
    then not considered as changed."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    try:
        with open(path, "rb") as f:
            if f.read() == content:
                return
    except FileNotFoundError:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)

"""Helpers shared by the build and the commands."""

import contextlib
import os
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import IO, Literal, Self, overload

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


class ProcessHelper:
    """A process kept running to answer requests. Requests are made in "with"
    blocks. Each process starts its own on first use."""

    def __init__(self, *args: str) -> None:
        self.args = args
        self.process: subprocess.Popen[str] | None = None
        self.stdin: IO[str]
        self.stdout: IO[str]
        self.stderr: IO[bytes]
        self.offset = 0

    def __enter__(self) -> Self:
        if self.process is None or self.process.poll() is not None:
            self.stop()
            self.start()
        return self

    def __exit__(self, error: type[BaseException] | None, *args: object) -> None:
        if error is not None:
            # Stop it, the rest of the answer may still be waiting
            self.stop()

    def start(self) -> None:
        # Node makes its error output non-blocking. When shared with us, our
        # own writes would fail. With a file in append mode, reading it does
        # not move where the process writes.
        stderr = tempfile.TemporaryFile("ab+")  # noqa: SIM115
        try:
            process = subprocess.Popen(
                self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr,
                encoding="utf-8",
            )
        except BaseException:
            stderr.close()
            raise
        assert process.stdin is not None and process.stdout is not None
        self.process, self.stdin, self.stdout = process, process.stdin, process.stdout
        self.stderr, self.offset = stderr, 0

    def stop(self) -> None:
        if self.process is None:
            return
        self.process.kill()
        self.process.wait()
        for stream in (self.stdin, self.stdout, self.stderr):
            with contextlib.suppress(OSError):
                stream.close()
        self.process = None

    def send(self, text: str) -> None:
        self.stdin.write(text)
        self.stdin.flush()

    def readline(self) -> str:
        line = self.stdout.readline()
        if not line:
            raise RuntimeError(f"{self.args[0]} stopped:\n{self.errors()}")
        return line

    def errors(self) -> str:
        """Error output since the previous call."""
        self.stderr.seek(self.offset)
        text = self.stderr.read().decode("utf-8", "replace")
        self.offset = self.stderr.tell()
        return text


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
    path = Path(path)
    try:
        if path.read_bytes() == content:
            return
    except FileNotFoundError:
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)

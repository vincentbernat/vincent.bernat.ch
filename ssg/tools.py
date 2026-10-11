"""Helpers shared by the build and the commands."""

import multiprocessing.util
import os
import subprocess
import tempfile
from collections.abc import Mapping
from typing import IO, Literal, overload

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
    """A process kept running to answer requests. Each process using it,
    including doit workers, starts its own on first use. It is stopped when
    this process exits."""

    def __init__(self, *args: str, quit: str = "") -> None:
        self.args = args
        # Input making the process exit, in addition to closing its input
        self.quit = quit
        self.pid = 0
        self.process: subprocess.Popen[str]
        self.stdin: IO[str]
        self.stdout: IO[str]
        self.stderr: IO[bytes]
        self.offset = 0

    def start(self) -> None:
        # Node makes its error output non-blocking. When shared with us, our
        # own writes would fail. With a file in append mode, reading it does
        # not move where the process writes.
        stderr = tempfile.TemporaryFile("ab+")  # noqa: SIM115
        process = subprocess.Popen(
            self.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
            encoding="utf-8",
        )
        assert process.stdin is not None and process.stdout is not None
        self.process, self.stdin, self.stdout = process, process.stdin, process.stdout
        self.stderr, self.offset, self.pid = stderr, 0, os.getpid()
        pid, stdin, quit = self.pid, self.stdin, self.quit

        def stop() -> None:
            # A forked process inherits this, the process is not its own
            if os.getpid() != pid:
                return
            if quit:
                stdin.write(quit)
            stdin.close()
            process.wait()
            stderr.close()

        multiprocessing.util.Finalize(None, stop, exitpriority=0)

    def send(self, text: str) -> None:
        if self.pid != os.getpid():
            self.start()
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
    try:
        with open(path, "rb") as f:
            if f.read() == content:
                return
    except FileNotFoundError:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)

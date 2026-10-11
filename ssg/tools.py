"""Helpers shared by the build and the commands."""

import contextlib
import ctypes
import os
import signal
import subprocess
import tempfile
import time
from collections.abc import Mapping
from typing import IO, ClassVar, Literal, Self, overload

from . import deps

PR_SET_PDEATHSIG = 1
prctl = ctypes.CDLL(None, use_errno=True).prctl


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
    blocks, from the main thread. Each process starts its own on first use. It
    is stopped after a minute without requests, and when this process exits."""

    IDLE = 60.0
    # There is only one timer, for the helper unused for the longest time
    helpers: ClassVar[list[ProcessHelper]] = []

    def __init__(self, *args: str) -> None:
        self.args = args
        self.process: subprocess.Popen[str] | None = None
        self.stdin: IO[str]
        self.stdout: IO[str]
        self.stderr: IO[bytes]
        self.offset = 0
        self.busy = False
        self.used = 0.0
        self.helpers.append(self)
        signal.signal(signal.SIGALRM, ProcessHelper.expired)

    def __enter__(self) -> Self:
        self.busy = True
        try:
            if self.process is None or self.process.poll() is not None:
                self.stop()
                self.start()
        except BaseException:
            self.busy = False
            raise
        return self

    def __exit__(self, error: type[BaseException] | None, *args: object) -> None:
        if error is not None:
            # Stop it, the rest of the answer may still be waiting
            self.stop()
        self.used = time.monotonic()
        self.busy = False
        if signal.getitimer(signal.ITIMER_REAL)[0] == 0:
            signal.setitimer(signal.ITIMER_REAL, self.IDLE)

    @classmethod
    def expired(cls, *args: object) -> None:
        """Stop unused helpers and set the timer for the next one."""
        now = time.monotonic()
        delays = []
        for helper in cls.helpers:
            if helper.process is None or helper.busy:
                continue
            delay = helper.used + helper.IDLE - now
            if delay > 0:
                delays.append(delay)
            else:
                helper.stop()
        if delays:
            signal.setitimer(signal.ITIMER_REAL, min(delays))

    @staticmethod
    def orphaned() -> None:
        """Kill the process when its parent exits."""
        prctl(PR_SET_PDEATHSIG, signal.SIGKILL)

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
                preexec_fn=self.orphaned,  # noqa: PLW1509
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
    try:
        with open(path, "rb") as f:
            if f.read() == content:
                return
    except FileNotFoundError:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)

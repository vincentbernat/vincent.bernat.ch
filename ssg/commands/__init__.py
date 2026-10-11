"""Commands not related to building the site."""

import contextlib
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

from .. import config

HOSTS = [
    "web02.luffy.cx",
    "web03.luffy.cx",
    "web04.luffy.cx",
    "web05.luffy.cx",
    "web06.luffy.cx",
]


FINAL = config.MODES["production"].output


class Exit(Exception):
    pass


def run(
    command: str, cwd: Path | None = None, capture: bool = False, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run a shell command."""
    result = subprocess.run(
        command,
        shell=True,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        check=False,
    )
    if check and result.returncode != 0:
        raise Exit(f"command failed: {command}")
    return result


def confirm(question: str, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        response = input(f"{question} [{suffix}] ").lower().strip()
        if not response:
            return default
        if response in ["y", "yes"]:
            return True
        if response in ["n", "no"]:
            return False
        print("I didn't understand you. Please specify '(y)es' or '(n)o'.")


@contextlib.contextmanager
def step(what: str) -> Iterator[None]:
    green = "\033[32;1m"
    blue = "\033[34;1m"
    yellow = "\033[33;1m"
    reset = "\033[0m"
    now = time.time()
    print(f"{blue}▶ {yellow}{what}{reset}...", file=sys.stderr)
    yield
    elapsed = int(time.time() - now)
    print(f"{blue}▶ {green}{what}{reset} ({elapsed}s)", file=sys.stderr)

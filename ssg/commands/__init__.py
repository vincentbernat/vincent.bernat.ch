"""Commands not related to building the site."""

import contextlib
import importlib
import inspect
import pkgutil
import re
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from doit.exceptions import TaskFailed

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


# doit task creators for the commands, by task name
TASKS: dict[str, Callable[[], dict[str, Any]]] = {}


def command[F: Callable[..., None]](name: str | None = None) -> Callable[[F], F]:
    """Make a function a doit task. The first sentence of its docstring
    describes it. Its keyword arguments are options, flags when their default
    is a bool. An argument without default gets the other words of the command
    line."""

    def register(function: F) -> F:
        def creator() -> dict[str, Any]:
            return task(function)

        TASKS[name or function.__name__] = creator
        return function

    return register


def tasks() -> dict[str, Callable[[], dict[str, Any]]]:
    """doit task creators of the commands defined in this package."""
    for module in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{__name__}.{module.name}")
    return TASKS


def task(function: Callable[..., None]) -> dict[str, Any]:
    """doit task running a command, with options from its signature."""
    summary = re.split(r"\.(?:\s|$)", inspect.getdoc(function) or "", maxsplit=1)[0]
    summary = " ".join(summary.split())
    params = []
    pos_arg = None
    for parameter in inspect.signature(function).parameters.values():
        if parameter.default is parameter.empty:
            pos_arg = parameter.name
            continue
        option = {
            "name": parameter.name,
            "long": parameter.name,
            "default": parameter.default,
        }
        if isinstance(parameter.default, bool):
            option["type"] = bool
        params.append(option)

    def action(**kwargs: Any) -> Any:
        try:
            function(**kwargs)
        except Exit as e:
            return TaskFailed(str(e))
        return None

    return {
        "doc": summary[:1].lower() + summary[1:],
        "actions": [action],
        "params": params,
        "pos_arg": pos_arg,
        "uptodate": [False],
        "verbosity": 2,
    }


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

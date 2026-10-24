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
    "web07.luffy.cx",
]


FINAL = config.MODES["production"].output


class Exit(Exception):
    pass


# Commands, by task name. "checks:vale" is part of the "checks" group, which
# runs all of them.
FUNCTIONS: dict[str, Callable[..., None]] = {}
# Tasks to run before a command
DEPENDENCIES: dict[str, list[str]] = {}


def command[F: Callable[..., None]](
    name: str | None = None, depends: list[str] | None = None
) -> Callable[[F], F]:
    """Make a function a doit task. The first sentence of its docstring
    describes it. Its keyword arguments are options, flags when their default
    is a bool. An argument without default gets the other words of the command
    line."""

    def register(function: F) -> F:
        key = (name or function.__name__).replace("_", "-")
        FUNCTIONS[key] = function
        DEPENDENCIES[key] = depends or []
        return function

    return register


Creator = Callable[[], dict[str, Any] | Iterator[dict[str, Any]]]


def tasks() -> dict[str, Creator]:
    """doit task creators of the commands defined in this package."""
    for module in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{__name__}.{module.name}")
    groups: dict[str, list[str]] = {}
    for name in FUNCTIONS:
        groups.setdefault(name.partition(":")[0], []).append(name)
    return {group: creator(group, names) for group, names in groups.items()}


def creator(group: str, names: list[str]) -> Creator:
    """doit task creator for a command or a group of commands. The docstring
    of the module describes a group."""
    if names == [group]:
        return lambda: task(group)

    def create() -> Iterator[dict[str, Any]]:
        module = sys.modules[FUNCTIONS[names[0]].__module__]
        yield {"name": None, "doc": summary(module.__doc__)}
        for name in names:
            yield task(name) | {"name": name.partition(":")[2]}

    return create


def summary(doc: str | None) -> str:
    """First sentence of a docstring, starting lowercase."""
    text = re.split(r"\.(?:\s|$)", inspect.cleandoc(doc or ""), maxsplit=1)[0]
    text = " ".join(text.split())
    return text[:1].lower() + text[1:]


def task(name: str) -> dict[str, Any]:
    """doit task running a command, with options from its signature."""
    function = FUNCTIONS[name]
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
        "doc": summary(function.__doc__),
        "actions": [action],
        "params": params,
        "pos_arg": pos_arg,
        "task_dep": DEPENDENCIES[name],
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

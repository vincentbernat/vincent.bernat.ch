import re
from collections.abc import Callable
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Protocol

class Slot(Protocol):
    def get(self) -> str: ...
    def put(self, value: str | None) -> None: ...

class Hyphenator:
    def __init__(
        self,
        path: Path | Traversable,
        names: dict[str, tuple[int, ...]],
        left: int,
        right: int,
    ) -> None: ...

class Run:
    slots: list[Slot]
    hyphenators: list[Hyphenator | None]
    starts: list[int]
    text: str
    def add(self, slot: Slot, hyphenator: Hyphenator | None = None) -> None: ...
    def opaque(self) -> None: ...
    def edit(self, changes: list[tuple[int, int, str]]) -> None: ...
    def sub(
        self, pattern: re.Pattern[str], repl: str | Callable[[re.Match[str]], str]
    ) -> None: ...
    def hyphenate(self) -> None: ...
    def write(self) -> None: ...

def last_line(texts: list[str]) -> list[str]: ...

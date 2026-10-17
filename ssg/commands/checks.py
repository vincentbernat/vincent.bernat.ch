"""Check content and code."""

import re

from .. import config
from . import Exit, command, run

FRONTMATTER_KEYS = (
    "layout",  # templating
    "title", "description", "uuid", "alias", "cover",  # identity
    "created", "attachments", "galleries", "tags",  # metadata
    "author", "bluesky", "github", "mastodon",  # attribution
    "featured", "popular", "listable", "notitle", "noindex",  # listing/visibility
    "comments", "share", "subscribe", "sidenotes",  # listing/visibility
    "csp", "headers", "html_class", "mime",  # headers
    "css", "js",  # assets
    "ai-usage",  # disclosure
)  # fmt: skip


@command("checks:vale")
def vale() -> None:
    """Check prose for forbidden words and common typos."""
    run("vale content/??", cwd=config.ROOT)


@command("checks:frontmatter")
def frontmatter(fix: bool = False) -> None:
    """Check frontmatter keys are known and ordered."""
    unordered = []
    for path in sorted(config.CONTENT.glob("??/**/*")):
        if path.suffix in (".yaml", ".yml") or not path.is_file():
            continue
        try:
            with path.open(encoding="utf-8") as f:
                lines = f.readlines()
            if lines[0].strip() != "---":
                continue
            end = next(i for i, line in enumerate(lines) if i and line.strip() == "---")
            blocks: list[tuple[int, list[str]]] = []
            for line in lines[1:end]:
                if m := re.match(r"([\w-]+):", line):
                    key = m.group(1)
                    if key not in FRONTMATTER_KEYS:
                        raise ValueError(f"unknown key {key}")
                    blocks.append((FRONTMATTER_KEYS.index(key), []))
                blocks[-1][1].append(line)
            if blocks == sorted(blocks):
                continue
            unordered.append(str(path))
            if fix:
                with path.open("w", encoding="utf-8") as out:
                    out.writelines(
                        lines[:1]
                        + [line for _, block in sorted(blocks) for line in block]
                        + lines[end:]
                    )
        except Exception as e:
            e.add_note(f"while checking {path}")
            raise
    if unordered and not fix:
        raise Exit(f"unordered frontmatter: {', '.join(unordered)}")


@command("checks:python")
def python() -> None:
    """Check Python code with ruff and mypy."""
    failed = [
        command
        for command in (
            "ruff check ssg",
            "ruff format --check ssg",
            "mypy",
        )
        if run(command, cwd=config.ROOT, check=False).returncode != 0
    ]
    if failed:
        raise Exit(f"failed: {', '.join(failed)}")

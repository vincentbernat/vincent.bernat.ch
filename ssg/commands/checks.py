"""Check content and code."""

import re
from pathlib import Path

import yaml

from .. import config
from . import Exit, command, run

FRONTMATTER_KEYS = (
    "layout",  # templating
    "title", "description", "uuid", "alias", "cover",  # identity
    "created", "attachments", "galleries", "tags", "src-ref",  # metadata
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


@command("checks:wip")
def scratch() -> None:
    """Check there is not WIP files."""
    if (config.ROOT / "scratch").exists():
        raise Exit("scratch directory still present at the root")
    if files := sorted(str(p) for p in config.CONTENT.glob("**/wip.*")):
        raise Exit(f"work-in-progress files: {', '.join(files)}")


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


@command("checks:tags")
def tags() -> None:
    """Check translations of a page have the same tags."""
    pages: dict[str, dict[str, tuple[Path, list[str]]]] = {}
    for path in sorted(config.CONTENT.glob("??/**/*.html")):
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            continue
        meta = yaml.safe_load(text[4 : text.index("\n---\n", 3)]) or {}
        if uuid := meta.get("uuid"):
            language = path.relative_to(config.CONTENT).parts[0]
            pages.setdefault(uuid, {})[language] = (path, meta.get("tags") or [])
    different = []
    for translations in pages.values():
        if len({tuple(sorted(t)) for _, t in translations.values()}) > 1:
            different.append(
                " vs ".join(
                    f"{p.relative_to(config.CONTENT)} ({', '.join(t)})"
                    for p, t in translations.values()
                )
            )
    if different:
        raise Exit("different tags:\n" + "\n".join(different))


@command("checks:python")
def python(benchmark: bool = False) -> None:
    """Check Python code with ruff and mypy, and run unit tests. With
    benchmark, also run benchmarks."""
    tests = "python -m unittest discover -s ssg/tests -t ."
    steps = [
        ("ruff", "ruff check ssg"),
        ("format", "ruff format --check ssg"),
        ("mypy", "mypy"),
        ("tests", tests),
    ]
    if benchmark:
        steps.append(("bench", f"{tests} -p 'bench_*.py'"))
    failed = [
        name
        for i, (name, args) in enumerate(steps)
        if run(
            args,
            cwd=config.ROOT,
            check=False,
            prefix=f"\033[{33 + i}m{name:6}\033[0m │ ",
        ).returncode
    ]
    if failed:
        raise Exit(f"failed: {', '.join(failed)}")

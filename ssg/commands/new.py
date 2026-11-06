"""Start a new article."""

import re
import shlex
import tempfile
import uuid

import yaml

from .. import config
from ..model.meta import FRONTMATTER
from . import Exit, command, run
from .checks import frontmatter

SKELETON = f"""\
---
title: "New WIP blog post"
description: |
  ...
uuid: {uuid.uuid4()}
---

<!--
  Target audiences:
    - ...

-->
"""


@command()
def new(finalize: str = "") -> None:
    """Create a draft article in content/en/blog/wip.html. With --finalize,
    rename the draft and merge its branch into main."""
    if finalize:
        publish(finalize)
        return
    path = config.CONTENT / "en" / "blog" / "wip.html"
    if path.exists():
        raise Exit(f"{path.relative_to(config.ROOT)} already exists")
    path.write_text(SKELETON, encoding="utf-8")
    run(f"git add {path}", cwd=config.ROOT)
    print(path.relative_to(config.ROOT))


def git(command: str, check: bool = True) -> str:
    result = run(f"git {command}", cwd=config.ROOT, capture=True, check=check)
    return result.stdout.strip()


def publish(name: str) -> None:
    if not re.fullmatch(r"[12][0-9]{3}-[a-z0-9-]+", name) or name == "wip":
        raise Exit(f"invalid name {name}")
    branch = git("branch --show-current")
    if not branch.startswith("article/"):
        raise Exit("not on an article branch")
    if git("status --porcelain"):
        raise Exit("uncommitted changes")
    article = config.CONTENT / "en" / "blog" / "wip.html"
    if not article.exists():
        raise Exit(f"no {article.relative_to(config.ROOT)}")
    match = FRONTMATTER.match(article.read_text(encoding="utf-8"))
    if not match:
        raise Exit(f"no frontmatter in {article.relative_to(config.ROOT)}")
    title = yaml.load(match.group(1), yaml.CSafeLoader)["title"]

    # Rebase on main, with the WIP commits squashed at the end.
    commits = [
        line.partition(" ")[::2]
        for line in git(
            "log --reverse --no-merges --format='%H %s' main.."
        ).splitlines()
    ]
    wip = [sha for sha, subject in commits if subject.startswith("WIP")]
    if not wip:
        raise Exit("no WIP commit")
    todo = [f"pick {sha}" for sha, subject in commits if not subject.startswith("WIP")]
    todo += [f"pick {wip[0]}"] + [f"fixup {sha}" for sha in wip[1:]]
    with tempfile.NamedTemporaryFile("w", suffix=".todo") as f:
        f.write("\n".join(todo) + "\n")
        f.flush()
        editor = shlex.quote(f"cp {shlex.quote(f.name)}")
        run(f"GIT_SEQUENCE_EDITOR={editor} git rebase -i main", cwd=config.ROOT)

    # Rename files and update references to them.
    replacements = []
    for path in sorted(config.CONTENT.glob("**/wip.*")):
        target = path.with_name(f"{name}{path.suffix}")
        if target.exists():
            raise Exit(f"{target.relative_to(config.ROOT)} already exists")
        git(f"mv {path} {target}")
        old = re.escape(path.name)
        replacements.append((re.compile(rf"(?<![\w-]){old}\b"), target.name))
    replacements.append(
        (re.compile(r"(self://[^\s)\]\"]*/)wip(?![\w.-])"), rf"\g<1>{name}")
    )
    files = git("grep -I -l -e wip -- content REUSE.toml", check=False).splitlines()
    for file in files:
        path = config.ROOT / file
        text = original = path.read_text(encoding="utf-8")
        for pattern, replacement in replacements:
            text = pattern.sub(replacement, text)
        if text != original:
            path.write_text(text, encoding="utf-8")
    frontmatter(fix=True)
    message = shlex.quote(f"article: {title}")
    git(f"commit -q -a --amend --reset-author -m {message}")

    git("switch -q main")
    git(f"merge -q --ff-only {branch}")
    git(f"branch -q -d {branch}")
    if git("ls-files scratch"):
        git("rm -q -r scratch")
        git("commit -q -m 'content: remove scratch directory'")

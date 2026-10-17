"""Start a new article."""

import uuid

from .. import config
from . import Exit, command, run

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
def new() -> None:
    """Create a draft article in content/en/blog/wip.html."""
    path = config.CONTENT / "en" / "blog" / "wip.html"
    if path.exists():
        raise Exit(f"{path.relative_to(config.ROOT)} already exists")
    path.write_text(SKELETON, encoding="utf-8")
    run(f"git add {path}", cwd=config.ROOT)
    print(path.relative_to(config.ROOT))

"""Check content for mistakes."""

import glob
import os
import re

from .. import config
from . import Exit, run

FRONTMATTER_KEYS = (
    "layout "  # templating
    "title description uuid alias cover "  # identity
    "created attachments galleries tags "  # metadata
    "author bluesky github mastodon "  # attribution
    "featured popular listable notitle noindex comments share subscribe sidenotes "  # listing/visibility
    "csp headers html_class mime "  # headers
    "css js "  # assets
    "ai-usage"  # disclosure
).split()


def check(fix=False):
    """Check content for mistakes."""
    # Check forbidden word or common typos
    run("vale content/??", cwd=config.ROOT)
    # Check frontmatters
    unordered = []
    for path in sorted(
        glob.glob(str(config.CONTENT / "??" / "**" / "*"), recursive=True)
    ):
        if path.endswith((".yaml", ".yml")) or not os.path.isfile(path):
            continue
        try:
            lines = open(path, encoding="utf-8").readlines()
            if lines[0].strip() != "---":
                continue
            end = next(i for i, line in enumerate(lines) if i and line.strip() == "---")
            blocks = []
            for line in lines[1:end]:
                if m := re.match(r"([\w-]+):", line):
                    key = m.group(1)
                    if key not in FRONTMATTER_KEYS:
                        raise ValueError(f"unknown key {key}")
                    blocks.append((FRONTMATTER_KEYS.index(key), []))
                blocks[-1][1].append(line)
            if blocks == sorted(blocks):
                continue
            unordered.append(path)
            if fix:
                with open(path, "w", encoding="utf-8") as out:
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

"""Search index."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from ..tools import run, write
from .files import copy

if TYPE_CHECKING:
    from ..model.site import Site


def extract(target: Path) -> None:
    """Extract the pagefind library by indexing an almost empty site."""
    with tempfile.TemporaryDirectory() as tmp:
        site = os.path.join(tmp, "site")
        os.makedirs(site)
        with open(os.path.join(site, "index.html"), "w") as f:
            f.write("<html><body><main data-pagefind-body>empty</main></body></html>")
        output = os.path.join(tmp, "out")
        run("pagefind", "--site", site, "--output-path", output, "--quiet")
        copy(os.path.join(output, "pagefind.js"), target)


UNWANTED = re.compile(
    r"^(pagefind-component.*|pagefind-modular.*|pagefind-ui.*|pagefind-worker.*"
    r"|pagefind-highlight\.js|pagefind\.js)$"
)


def index(site: Site) -> None:
    """Index the site for searching."""
    out = site.mode.output
    destination = out / "media" / "pagefind"
    site.mode.cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=site.mode.cache) as tmp:
        run(
            "pagefind",
            "--site",
            out,
            "--exclude-selectors=.headerlink",
            "--output-path",
            tmp,
            "--quiet",
        )
        shutil.rmtree(destination, ignore_errors=True)
        os.makedirs(destination)
        files = []
        for name in sorted(os.listdir(tmp)):
            if not UNWANTED.match(name):
                shutil.move(os.path.join(tmp, name), destination / name)
                files.append(name)
    write(site.mode.cache / "pagefind.json", json.dumps(files))


def exist(site: Site) -> bool:
    """Check the files of the search index exist."""
    try:
        with open(site.mode.cache / "pagefind.json") as f:
            files = json.load(f)
    except FileNotFoundError:
        return False
    destination = site.mode.output / "media" / "pagefind"
    return all(os.path.exists(destination / name) for name in files)

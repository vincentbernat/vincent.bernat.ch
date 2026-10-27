"""Search index."""

from __future__ import annotations

import json
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
        site = Path(tmp) / "site"
        site.mkdir()
        (site / "index.html").write_text(
            "<html><body><main data-pagefind-body>empty</main></body></html>"
        )
        output = Path(tmp) / "out"
        run("pagefind", "--site", site, "--output-path", output, "--quiet")
        copy(output / "pagefind.js", target)


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
            "--exclude-selectors=[hidden]",
            "--output-path",
            tmp,
            "--quiet",
        )
        shutil.rmtree(destination, ignore_errors=True)
        destination.mkdir(parents=True)
        files = []
        for path in sorted(Path(tmp).iterdir()):
            if not UNWANTED.match(path.name):
                path.move(destination / path.name)
                files.append(path.name)
    write(site.mode.cache / "pagefind.json", json.dumps(files))


def exist(site: Site) -> bool:
    """Check the files of the search index exist."""
    try:
        files = json.loads((site.mode.cache / "pagefind.json").read_text())
    except FileNotFoundError:
        return False
    destination = site.mode.output / "media" / "pagefind"
    return all((destination / name).exists() for name in files)

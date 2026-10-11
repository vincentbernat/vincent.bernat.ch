"""Process media files: stylesheets, scripts and SVG images."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .. import templates
from ..tools import run

if TYPE_CHECKING:
    from ..model.resource import Resource
    from ..model.site import Site


def text(site: Site, resource: Resource) -> str:
    """Text of a resource before processing specific to its kind."""
    output = templates.render_body(site, resource)
    return "".join([output] + [r.source_text for r in resource.combined])


def python(site: Site, resource: Resource) -> str:
    """Run a Python resource. It defines `run(site, resource)` returning the
    content."""
    namespace: dict[str, Any] = {}
    exec(resource.source_text, namespace)
    return namespace["run"](site, resource)


def js(site: Site, text: str) -> str:
    args = ["esbuild", "--target=es2015", "--log-level=warning"]
    if site.mode.production:
        args.append("--minify")
    return run(*args, input=text)

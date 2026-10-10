"""Process media files: stylesheets, scripts and SVG images."""

from .. import templates
from ..tools import run


def text(site, resource):
    """Text of a resource before processing specific to its kind."""
    output = templates.render_body(site, resource)
    return "".join([output] + [r.content for r in resource.combined])


def python(site, resource):
    """Run a Python resource. It defines `run(site, resource)` returning the
    content."""
    namespace = {}
    exec(resource.content, namespace)
    return namespace["run"](site, resource)


def js(site, text):
    args = ["esbuild", "--target=es2015", "--log-level=warning"]
    if site.mode.production:
        args.append("--minify")
    return run(*args, input=text)

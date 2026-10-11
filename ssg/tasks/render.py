"""Render pages, articles and media files."""

import json
import sys

from .. import deps, fonts, html, markdown, templates
from ..media import css, js, python, svg, text
from ..tools import write


def media(site, resource):
    deps.record_resource(resource)
    deps.record_code()
    for source in [resource, *resource.combined]:
        deps.record_content(source)
    if resource.python:
        deps.getenv("FONTCONFIG_FILE", "")
        content = python(site, resource)
    else:
        content = text(site, resource)
        match resource.kind:
            case "css":
                content = css.process(site, content)
            case "js":
                content = js(site, content)
            case "svg":
                content = svg.process(content)
    write(site.generated[resource.media_path], content)


def fragment(site, resource, target):
    markdown.collected = {"monospace": set(), "regular": set(), "references": set()}
    try:
        deps.record_resource(resource)
        deps.record_code()
        deps.record_content(resource)
        output = templates.render_article(site, resource)
        collected = markdown.collected
    finally:
        markdown.collected = None
    for label in sorted(collected["references"]):
        print(f"{resource.path}: unknown reference: [{label}]", file=sys.stderr)
    if collected["references"] and site.mode.production:
        return False
    write(
        target,
        json.dumps(
            {
                "html": output,
                "glyphs": {
                    kind: "".join(sorted(collected[kind])) for kind in fonts.KINDS
                },
            },
            ensure_ascii=False,
        ),
    )


def page(site, resource, fragment, target):
    context = {}
    if fragment:
        with open(fragment, encoding="utf-8") as f:
            context["formatted_article"] = json.load(f)["html"]
    deps.record_resource(resource)
    deps.record_code()
    deps.record_content(resource)
    output = templates.render(site, resource, **context)
    if resource.kind == "html":
        output = html.page(site, resource, output)
    elif resource.name == "atom.xml":
        output = html.feed(site, resource, output)
    write(target, output)

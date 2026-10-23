"""Render pages, articles and media files."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .. import deps, fonts, html, markdown, templates
from ..media import css, js, python, svg, text
from ..tools import write

if TYPE_CHECKING:
    from ..model.resource import Resource
    from ..model.site import Site


def media(site: Site, resource: Resource) -> None:
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


def fragment(site: Site, resource: Resource, target: Path) -> bool:
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
    return True


def page(site: Site, resource: Resource, fragment: Path | None, target: Path) -> None:
    context = {}
    if fragment:
        content = fragment.read_text(encoding="utf-8")
        context["formatted_article"] = json.loads(content)["html"]
    deps.record_resource(resource)
    deps.record_code()
    deps.record_content(resource)
    output = templates.render(site, resource, **context)
    if resource.kind == "html":
        output = html.page(site, resource, output)
    elif resource.meta.get("layout") == "atom.j2":
        output = html.feed(site, resource, output)
    write(target, output)

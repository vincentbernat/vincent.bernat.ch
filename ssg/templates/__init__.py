"""Jinja templates."""

from __future__ import annotations

import functools
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import jinja2
import jinja2.meta

from .. import config, deps
from ..typography import typogrify
lazy from .. import markdown

if TYPE_CHECKING:
    from ..model.resource import Resource
    from ..model.site import Site

# Layout displaying the body of a resource as an article, written in Markdown
ARTICLE_LAYOUT = "base.j2"
FILTERS: dict[str, Callable[..., Any]] = {}
GLOBALS: dict[str, Callable[..., Any]] = {}


def jinja_filter[F: Callable[..., Any]](function: F) -> F:
    """Make a function available as a filter in templates."""
    FILTERS[function.__name__] = function
    return function


def jinja_global[F: Callable[..., Any]](function: F) -> F:
    """Make a function available in templates."""
    GLOBALS[function.__name__] = function
    return function


jinja_filter(typogrify)


class Loader(jinja2.FileSystemLoader):
    """Load layouts and, for content, the text after the frontmatter."""

    def __init__(self, site: Site) -> None:
        super().__init__(str(config.LAYOUT))
        self.site = site

    def get_source(
        self, environment: jinja2.Environment, template: str
    ) -> tuple[str, str, Callable[[], bool]]:
        resource = self.site.resources.get(template)
        if resource is None:
            return super().get_source(environment, template)
        # Content does not change while building
        return resource.body(), str(resource.source), lambda: True


@functools.cache
def environment(site: Site) -> jinja2.Environment:
    env = jinja2.Environment(
        loader=Loader(site),
        undefined=jinja2.ChainableUndefined,
        trim_blocks=True,
        extensions=["jinja2.ext.do", "jinja2.ext.loopcontrols"],
    )
    env.globals.update(
        GLOBALS,
        site=site,
        base=config.BASE,
        languages=config.LANGUAGES,
        media_url=site.media_url,
        content_url=site.content_url,
    )
    env.filters.update(FILTERS)
    return env


def render_body(site: Site, resource: Resource) -> str:
    """Render the text of a resource."""
    if not resource.uses_template:
        return resource.body()
    for path in article_layouts(resource):
        deps.record_file(path)
    template = environment(site).get_template(resource.path)
    return template.render(resource=resource, node=resource.node)


def render_article(site: Site, resource: Resource) -> str:
    """Render the text of a resource, then convert it from Markdown."""
    text = render_body(site, resource)
    meta = resource.meta
    return typogrify(
        markdown.convert(text, site, meta.get("l10n"), meta.get("sources"))
    )


def render(site: Site, resource: Resource, **context: Any) -> str:
    """Render a resource inside its layout. With the article layout, the
    article is in the context."""
    layout = resource.meta.get("layout")
    if not layout:
        return render_body(site, resource)
    for path in page_layouts(resource):
        deps.record_file(path)
    if not is_article_layout(site, layout):
        context["content"] = render_body(site, resource)
    template = environment(site).get_template(layout)
    return template.render(resource=resource, node=resource.node, **context)


def is_article_layout(site: Site, layout: str | None) -> bool:
    """Tell if a layout displays the body of a resource as an article."""
    if not layout:
        return False
    return layout == ARTICLE_LAYOUT or ARTICLE_LAYOUT in referenced(site, layout)


def article_layouts(resource: Resource) -> list[str]:
    """Layout files used to render the article of a resource."""
    return layout_files(resource.site, resource.path)


def page_layouts(resource: Resource) -> list[str]:
    """Layout files used to render a resource. With the article layout, the
    article is already rendered."""
    layout = resource.meta.get("layout")
    names = set()
    if layout:
        names |= {layout} | referenced(resource.site, layout)
    if not is_article_layout(resource.site, layout) and resource.uses_template:
        names |= referenced(resource.site, resource.path)
    return [str(config.LAYOUT / name) for name in sorted(names)]


def layout_files(site: Site, name: str) -> list[str]:
    return [str(config.LAYOUT / n) for n in sorted(referenced(site, name))]


# Tags referencing another template
REFERENCE_TAG = re.compile(r"\{%[-+]?\s*(?:extends|include|import|from)\b")


@functools.cache
def referenced(site: Site, name: str) -> frozenset[str]:
    """Layouts a template extends, includes or imports, directly or not."""
    env = environment(site)
    source = Loader(site).get_source(env, name)[0]
    if not REFERENCE_TAG.search(source):
        return frozenset()
    result = set()
    for ref in jinja2.meta.find_referenced_templates(env.parse(source)):
        if ref is None:
            # Name only known while rendering
            return frozenset(p.name for p in config.LAYOUT.glob("*.j2"))
        result |= {ref} | referenced(site, ref)
    return frozenset(result)


def fragment_path(resource: Resource) -> Path:
    """Where the rendered article of a resource is stored."""
    return resource.site.mode.cache / "fragments" / (resource.path + ".json")


@jinja_global
def article(resource: Resource) -> str:
    """Rendered article of another resource."""
    path = fragment_path(resource)
    deps.record_file(path)
    return json.loads(path.read_text(encoding="utf-8"))["html"]


# Register filters and functions
from . import filters, functions  # noqa: F401

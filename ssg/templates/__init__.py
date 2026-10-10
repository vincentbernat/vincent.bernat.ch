"""Jinja templates."""

import functools
import json

import jinja2
import jinja2.meta

from .. import config, deps, markdown
from ..typography import typogrify

# Layout displaying the body of a resource as an article, written in Markdown
ARTICLE_LAYOUT = "base.j2"
FILTERS = {}
GLOBALS = {}


def jinja_filter(function):
    """Make a function available as a filter in templates."""
    FILTERS[function.__name__] = function
    return function


def jinja_global(function):
    """Make a function available in templates."""
    GLOBALS[function.__name__] = function
    return function


jinja_filter(typogrify)


class Loader(jinja2.FileSystemLoader):
    """Load layouts and, for content, the text after the frontmatter."""

    def __init__(self, site):
        super().__init__(str(config.LAYOUT))
        self.site = site

    def get_source(self, environment, template):
        resource = self.site.resources.get(template)
        if resource is None:
            return super().get_source(environment, template)
        # Content does not change while building
        return resource.body(), str(resource.source), lambda: True


@functools.cache
def environment(site):
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


def render_body(site, resource):
    """Render the text of a resource."""
    if not resource.uses_template:
        return resource.body()
    for path in article_layouts(resource):
        deps.record_file(path)
    template = environment(site).get_template(resource.path)
    return template.render(resource=resource, node=resource.node)


def render_article(site, resource):
    """Render the text of a resource, then convert it from Markdown."""
    text = render_body(site, resource)
    return typogrify(markdown.convert(text, site, resource.meta.get("l10n")))


def render(site, resource, **context):
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


def is_article_layout(site, layout):
    """Tell if a layout displays the body of a resource as an article."""
    if not layout:
        return False
    return layout == ARTICLE_LAYOUT or ARTICLE_LAYOUT in referenced(site, layout)


def article_layouts(resource):
    """Layout files used to render the article of a resource."""
    return layout_files(resource.site, resource.path)


def page_layouts(resource):
    """Layout files used to render a resource. With the article layout, the
    article is already rendered."""
    layout = resource.meta.get("layout")
    names = set()
    if layout:
        names |= {layout} | referenced(resource.site, layout)
    if not is_article_layout(resource.site, layout) and resource.uses_template:
        names |= referenced(resource.site, resource.path)
    return [str(config.LAYOUT / name) for name in sorted(names)]


def layout_files(site, name):
    return [str(config.LAYOUT / n) for n in sorted(referenced(site, name))]


@functools.cache
def referenced(site, name):
    """Layouts a template extends, includes or imports, directly or not."""
    env = environment(site)
    source = env.loader.get_source(env, name)[0]
    result = set()
    for ref in jinja2.meta.find_referenced_templates(env.parse(source)):
        if ref is None:
            # Name only known while rendering
            return frozenset(p.name for p in config.LAYOUT.glob("*.j2"))
        result |= {ref} | referenced(site, ref)
    return frozenset(result)


def fragment_path(resource):
    """Where the rendered article of a resource is stored."""
    return resource.site.mode.cache / "fragments" / (resource.path + ".json")


@jinja_global
def article(resource):
    """Rendered article of another resource."""
    path = fragment_path(resource)
    deps.record_file(path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)["html"]


# Register filters and functions
from . import filters, functions  # noqa: E402, F401

# -*- coding: utf-8 -*-
import os
import jinja2
import re
from babel.dates import format_date
from distutils.version import LooseVersion


def human_date(dt, locale='en', format=None):
    """Convert an ISO 8601 date to a more readable version."""
    if format is None:
        return format_date(dt, 'MMMM yyyy', locale=locale)
    else:
        return format_date(dt, format=format, locale=locale)


def same_tag(resource, attribute, skip=0):
    """Returns the next resource with at least a common tag using the
    provided attribute to iterate over resources.
    """
    tags = {t.name
            for t in getattr(resource, 'tags', [])
            if t.name != 'outdated' and t.name != 'unclassified'}
    candidate = resource
    while candidate:
        candidate = getattr(candidate, attribute, None)
        if skip:
            skip -= 1
            continue
        ctags = {t.name for t in getattr(candidate, 'tags', [])}
        if 'outdated' in ctags:
            continue
        if len(tags & ctags) > 0:
            break
    return candidate


def media_listing(resources, directory):
    """Version-sort media resources contained in directory."""
    resources = [r
                 for r in resources
                 if r.source_file.parent.path.endswith("/media/" + directory)]
    to_sort = [{"resource": r,
                "version": LooseVersion(r.relative_path)}
               for r in resources]
    to_sort.sort(key=lambda x: x["version"])
    return [r["resource"] for r in to_sort]


def mastodon_href(handle):
    """Turn a mastodon handle into an href (very naive)."""
    mo = re.match(r"@(.*)@(.*)", handle)
    assert(mo)
    return f"https://{mo.group(2)}/@{mo.group(1)}"


@jinja2.contextfunction
def include_file(ctx, name):
    target = os.path.join(str(ctx.parent['node']), name)
    with open(target, "r") as f:
        return jinja2.Markup(f.read())

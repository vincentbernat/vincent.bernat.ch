# -*- coding: utf-8 -*-
from babel.dates import format_date


def humandate(dt, locale='en', format=None):
    """Convert an ISO 8601 date to a more readable version."""
    if format is None:
        return format_date(dt, 'MMMM yyyy', locale=locale)
    else:
        return format_date(dt, format=format, locale=locale)


def samecategory(resource, attribute, skip=0):
    """Returns the next resource in the same category using the provided
    attribute to iterate over resources."""
    tags = {t.name
            for t in getattr(resource, 'tags', [])
            if t.name != 'outdated'}
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

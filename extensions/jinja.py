# -*- coding: utf-8 -*-
from babel.dates import format_date


def humandate(dt, locale='en', format=None):
    """Convert an ISO 8601 date to a more readable version."""
    if format is None:
        return format_date(dt, 'MMMM yyyy', locale=locale)
    else:
        return format_date(dt, format=format, locale=locale)

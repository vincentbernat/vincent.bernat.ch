from babel.dates import format_date


def humandate(dt, locale='en', format=None):
    if format is None:
        return format_date(dt, 'MMMM yyyy', locale=locale)
    else:
        return format_date(dt, format=format, locale=locale)

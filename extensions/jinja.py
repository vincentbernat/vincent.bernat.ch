from babel.dates import format_date


def humandate(dt, locale='en'):
    return format_date(dt, locale=locale, format='long')

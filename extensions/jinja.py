from babel.dates import format_date
from pyquery import PyQuery as pq
from lxml.html import tostring as html2str


def humandate(dt, locale='en', format=None):
    """Convert an ISO 8601 date to a more readable version."""
    if format is None:
        return format_date(dt, 'MMMM yyyy', locale=locale)
    else:
        return format_date(dt, format=format, locale=locale)


def footnotes2asides(html):
    """Copy footnotes as sidenotes, to be displayed when there is enough
    place for them."""
    d = pq(u'<div>{}</div>'.format(html))
    footnotes = d('.footnote ol')
    for ref in d.items("sup[id^=fnref-]"):
        name = ref.attr.id[6:]
        fn = footnotes('li[id=fn-{}]'.format(name))
        assert(fn)
        parent = ref.parents().eq(3)  # html, body, div, HERE
        sidenote = pq('<aside/>')
        sidenote.attr.role = "note"
        sidenote.attr.class_ = "lf-sidenote"
        sidenote.html(u'<sup class="lf-refmark">{}</sup>{}'.format(
            ref.text(), fn.html()))
        sidenote.insert_before(parent)
    return html2str(d[0], encoding='unicode')[5:-6]

# -*- coding: utf-8 -*-
import re
import subprocess
import HTMLParser
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
        sidenote.attr['aria-hidden'] = "true"
        sidenote.attr.class_ = "lf-sidenote"
        sidenote.html(u'<sup class="lf-refmark">{}</sup>{}'.format(
            ref.text(), fn.html()))
        sidenote("a.footnote-backref").remove()
        sidenote.insert_before(parent)
    return html2str(d[0], encoding='unicode')[5:-6]


katex_re = re.compile(ur'(?<!\\)·(.+?)·', re.DOTALL)
katex_pr = [None]
katex_js = """
var katex = require('katex');
var split = require('split');
process.stdin.pipe(split('\\0', null, { trailing: false })).on('data', function(latex) {
  process.stdout.write(katex.renderToString(latex));
  process.stdout.write('\\0');
});
"""

def katex(html):
    """Extract LaTeX snippets and run them through KaTeX."""
    return katex_re.sub(katex_render, html)

def katex_render(mo):
    formula = HTMLParser.HTMLParser().unescape(mo.group(1))
    if katex_pr[0] is None:
        katex_pr[0] = subprocess.Popen(['node', '-e', katex_js],
                                       stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE)
    # Assume input is small enough
    katex_pr[0].stdin.write(formula.encode('utf-8'))
    katex_pr[0].stdin.write('\0')
    katex_pr[0].stdin.flush()
    # Get answer
    answer = ""
    while True:
        char = katex_pr[0].stdout.read(1)
        if char == '':
            raise RuntimeError('unexpected stream end')
        if char == '\0':
            break
        answer += char
    answer = answer.decode('utf-8')
    return answer

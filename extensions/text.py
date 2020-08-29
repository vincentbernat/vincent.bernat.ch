# -*- coding: utf-8 -*-
import re
import subprocess
import html.parser

from pyquery import PyQuery as pq
from hyde.plugin import Plugin


class FootnotesPlugin(Plugin):
    """Copy footnotes as asides."""
    def text_resource_complete(self, resource, text):
        if resource.source_file.kind != 'html':
            return

        d = pq(text, parser='html')
        footnotes = d('.footnote ol')

        # Pop out orphaned backlinks
        backrefs = footnotes('.footnote-backref')
        for backref in backrefs.items():
            parent = backref.parent()
            if len(parent.contents()) == 1:
                # We only have the <a> link
                parent.replace_with(backref)

        # Create sidenotes
        for ref in d.items("sup[id^=fnref-]"):
            name = ref.attr.id[6:]
            fn = footnotes('li[id=fn-{}]'.format(name))
            assert(fn)
            parents = ref.parents()
            for i in range(len(parents)-1):
                if parents.eq(i).attr.id == 'lf-text':
                    parent = parents.eq(i+1)
            sidenote = pq('<aside/>')
            sidenote.attr.role = "note"
            sidenote.attr['hidden'] = "hidden"
            sidenote.attr.class_ = "lf-sidenote"
            sidenote.html(u'<sup class="lf-refmark">{}</sup>{}'.format(
                ref.text(), fn.html()))
            sidenote("a.footnote-backref").remove()
            sidenote.insert_before(parent)
        return u'<!DOCTYPE html>\n' + d.outer_html()


class LatexPlugin(Plugin):
    """Transform LaTeX formula with KaTeX."""

    JS = """
var katex = require('katex');
var split = require('split');
process.stdin.pipe(split('\\0', null, { trailing: false })).on('data', function(latex) {
  process.stdout.write(katex.renderToString(latex));
  process.stdout.write('\\0');
});
"""
    RE = re.compile(r'(?<!\\)·(.+?)·', re.DOTALL)
    PR = None

    def katex_render(self, mo):
        formula = html.parser.HTMLParser().unescape(mo.group(1))
        if self.PR is None:
            self.PR = subprocess.Popen(['node', '-e', self.JS],
                                       stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE)
        # Assume input is small enough
        self.PR.stdin.write(formula.encode('utf-8'))
        self.PR.stdin.write(b'\0')
        self.PR.stdin.flush()
        # Get answer
        answer = b""
        while True:
            char = self.PR.stdout.read(1)
            if char == b'':
                raise RuntimeError('unexpected stream end')
            if char == b'\0':
                break
            answer += char
        answer = answer.decode('utf-8')
        return answer

    def text_resource_complete(self, resource, text):
        if resource.source_file.kind != 'html':
            return
        return self.RE.sub(self.katex_render, text)

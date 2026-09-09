r"""Render LaTeX formulas with KaTeX.

A formula is written between $` and `$, like $`\sqrt{2}`$. This syntax is from
GitLab.

"""

import json
import subprocess

import markdown

# Read formulas from stdin, write the answers to stdout as JSON, NUL as
# separator.
RENDERER = """
var katex = require('katex');
var split = require('split');
process.stdin.pipe(split('\\0', null, { trailing: false })).on('data', function(latex) {
  var answer;
  try {
    answer = { html: katex.renderToString(latex) };
  } catch (e) {
    answer = { error: e.message };
  }
  process.stdout.write(JSON.stringify(answer));
  process.stdout.write('\\0');
});
"""

renderer = None


def render(formula):
    """Turn one LaTeX formula into HTML."""
    global renderer
    if renderer is None:
        renderer = subprocess.Popen(
            ["node", "-e", RENDERER], stdin=subprocess.PIPE, stdout=subprocess.PIPE
        )
    # Assume input is small enough
    renderer.stdin.write(formula.encode("utf-8"))
    renderer.stdin.write(b"\0")
    renderer.stdin.flush()
    answer = b""
    while True:
        char = renderer.stdout.read(1)
        if char == b"":
            raise RuntimeError("unexpected stream end")
        if char == b"\0":
            break
        answer += char
    answer = json.loads(answer)
    if "error" in answer:
        raise RuntimeError(f"cannot render {formula!r}: {answer['error']}")
    return answer["html"]


class KaTeXPattern(markdown.inlinepatterns.InlineProcessor):
    def __init__(self, md):
        super().__init__(r"(?<!\\)\$`(.+?)`\$", md)

    def handleMatch(self, m, data):
        formula = f"<x-latex>{render(m.group(1))}</x-latex>"
        return self.md.htmlStash.store(formula), m.start(0), m.end(0)


class KaTeXExtension(markdown.Extension):
    def extendMarkdown(self, md):
        # Needs to come before backtick and escape matching: a formula is not
        # code and \ is pretty important in LaTeX
        md.inlinePatterns.register(KaTeXPattern(md), "katex", 195)


def makeExtension(**kwargs):
    return KaTeXExtension(**kwargs)

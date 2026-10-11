r"""Render LaTeX formulas with KaTeX.

A formula is written between $` and `$, like $`\sqrt{2}`$. This syntax is from
GitLab.

"""

import json
import multiprocessing.util
import subprocess
import tempfile

import markdown

# Read one formula per line as a JSON string, write one answer per line as
# JSON
RENDERER = """
const katex = require("katex");
const lines = require("readline").createInterface({ input: process.stdin });
lines.on("line", (line) => {
  let answer;
  try {
    answer = { html: katex.renderToString(JSON.parse(line)) };
  } catch (e) {
    answer = { error: e.message };
  }
  process.stdout.write(JSON.stringify(answer) + "\\n");
});
"""

renderer = None
errors = None


def stop():
    renderer.stdin.close()
    renderer.wait()
    errors.close()


def render(formula):
    """Turn one LaTeX formula into HTML."""
    global renderer, errors
    if renderer is None:
        # Node makes its standard error non-blocking. When shared with us,
        # our own writes would fail.
        errors = tempfile.TemporaryFile()
        renderer = subprocess.Popen(
            ["node", "-e", RENDERER],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=errors,
            encoding="utf-8",
        )
        # Stopped when the process exits, including doit workers
        multiprocessing.util.Finalize(None, stop, exitpriority=0)
    renderer.stdin.write(json.dumps(formula) + "\n")
    renderer.stdin.flush()
    line = renderer.stdout.readline()
    if not line:
        errors.seek(0)
        message = errors.read().decode("utf-8", "replace")
        raise RuntimeError(f"KaTeX renderer stopped: {message}")
    answer = json.loads(line)
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

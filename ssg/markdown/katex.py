r"""Render LaTeX formulas with KaTeX.

A formula is written between $` and `$, like $`\sqrt{2}`$. This syntax is from
GitLab.

"""

import json
import re
from typing import Any
from xml.etree.ElementTree import Element

import markdown

from .. import deps
from ..tools import ProcessHelper

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

renderer = ProcessHelper("node", "-e", RENDERER)


def render(formula: str) -> str:
    """Turn one LaTeX formula into HTML."""
    deps.tool("node")
    with renderer:
        renderer.send(json.dumps(formula) + "\n")
        answer = json.loads(renderer.readline())
    if "error" in answer:
        raise RuntimeError(f"cannot render {formula!r}: {answer['error']}")
    return answer["html"]


class KaTeXPattern(markdown.inlinepatterns.InlineProcessor):
    def __init__(self, md: Any) -> None:
        super().__init__(r"(?<!\\)\$`(.+?)`\$", md)

    def handleMatch(  # type: ignore[override]
        self, m: re.Match[str], data: str
    ) -> tuple[Element | str | None, int | None, int | None]:
        formula = f"<x-latex>{render(m.group(1))}</x-latex>"
        return self.md.htmlStash.store(formula), m.start(0), m.end(0)


class KaTeXExtension(markdown.Extension):
    def extendMarkdown(self, md: Any) -> None:
        # Needs to come before backtick and escape matching: a formula is not
        # code and \ is pretty important in LaTeX
        md.inlinePatterns.register(KaTeXPattern(md), "katex", 195)


def makeExtension(**kwargs: Any) -> KaTeXExtension:
    return KaTeXExtension(**kwargs)

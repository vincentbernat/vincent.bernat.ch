"""Renders the article's code blocks the way the site does.

The stage shows the same markup as the published page, so the packet dumps look
identical: same lexer, same .codehilite classes, same highlighted lines.

    python3 scratch/highlight.py

Writes scratch/blocks/<segment id>.html.
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pygments import highlight  # noqa: E402
from pygments.formatters import HtmlFormatter  # noqa: E402
from pygments.lexers import get_lexer_by_name  # noqa: E402

# Registers the site's own lexers, Wireshark among them.
from extensions.pygments import WiresharkLexer  # noqa: E402,F401

ROOT = pathlib.Path(__file__).resolve().parent
BLOCKS = ROOT / "out" / "blocks"

LEXERS = {"wireshark": WiresharkLexer()}


def lexer_for(name):
    if name in LEXERS:
        return LEXERS[name]
    return get_lexer_by_name(name)


def main():
    segments = json.loads((ROOT / "out" / "segments.json").read_text())
    BLOCKS.mkdir(parents=True, exist_ok=True)
    for old in BLOCKS.glob("*.html"):
        old.unlink()

    written = 0
    for segment in segments["segments"]:
        body = segment.get("body")
        if not body:
            continue
        visual = segment["visual"]
        lang = visual.get("lang", "text")
        formatter = HtmlFormatter(
            cssclass="codehilite",
            hl_lines=visual.get("highlights") or [],
            nowrap=False,
        )
        html = highlight(body, lexer_for(lang), formatter)
        # The site wraps the block with the language, via codehilite_lang, and
        # markdown puts a <code> inside the <pre>. Match both so the stage and
        # the published page style the block the same way.
        html = html.replace(
            '<div class="codehilite">',
            f'<div class="language-{lang} codehilite">',
            1,
        )
        if "<code>" not in html:
            html = html.replace("<pre><span></span>", "<pre><span></span><code>", 1)
            html = html.replace("</pre>", "</code></pre>", 1)
        (BLOCKS / f"{segment['slug']}.html").write_text(html)
        written += 1

    print(f"rendered {written} code blocks into scratch/out/blocks/")


if __name__ == "__main__":
    main()

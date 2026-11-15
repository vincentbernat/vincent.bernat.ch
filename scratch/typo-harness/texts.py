"""Write texts.json with the Verne paragraph of wip.html, as processed by
typography.py and as raw text without soft hyphens and the last-line no-break
space.

Run with a Python where ssg.html.ctypography matches the current .pyx:

    PYTHONPATH=<dir with ssg/> python3 scratch/typo-harness/texts.py
"""

import json
import pathlib
import re

import lxml.html

from ssg.html import typography

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHY = "\u00ad"  # SOFT HYPHEN
NBSP = "\u00a0"  # NO-BREAK SPACE

source = (ROOT / "content/en/blog/wip.html").read_text()
match = re.search(r"\n> (Le marin pressa.*?)\n> \{lang=fr\}", source, re.S)
assert match
text = re.sub(r"\n> ", " ", match.group(1))

root = lxml.html.fromstring(
    f'<html lang="fr"><body><div class="lf-text"><p>{text}</p></div></body></html>'
)
typography.fix(root)
p = root.find(".//p")
assert p is not None
processed = p.text_content()

# Only the last-line rule leaves a NBSP here, the others became NNBSP
assert processed.count(NBSP) == 1, processed.count(NBSP)
raw = processed.replace(SHY, "").replace(NBSP, " ")

out = pathlib.Path(__file__).with_name("texts.json")
out.write_text(
    json.dumps({"processed": processed, "raw": raw}, ensure_ascii=False, indent=2)
    + "\n"
)
print(raw)

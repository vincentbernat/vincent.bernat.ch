"""Tests for ssg.html.codebreaks."""

import unittest

import lxml.html

from ssg.html import codebreaks


def render(html: str, cls: str = "lf-text") -> str:
    root = lxml.html.fromstring(f'<div class="{cls}">{html}</div>')
    codebreaks.fix(root)
    output = lxml.html.tostring(root, encoding="unicode")
    return output[len(f'<div class="{cls}">') : -len("</div>")]


class TestCodeBreaks(unittest.TestCase):
    def test_fix(self) -> None:
        cases = [
            (
                "<p><code>prometheus.remote_write</code></p>",
                "<p><code>prometheus<wbr>.remote<wbr>_write</code></p>",
            ),
            (
                "<p><code>/etc/systemd/system</code></p>",
                "<p><code>/etc<wbr>/systemd<wbr>/system</code></p>",
            ),
            # Numbers, short parts and repeated marks
            ("<p><code>1.2.3</code></p>", "<p><code>1.2.3</code></p>"),
            ("<p><code>a.b</code></p>", "<p><code>a.b</code></p>"),
            ("<p><code>..foo..bar</code></p>", "<p><code>..foo<wbr>..bar</code></p>"),
            # Elements inside code
            (
                "<p><code><span>discovery</span>.kubernetes_sd</code></p>",
                "<p><code><span>discovery</span>.kubernetes<wbr>_sd</code></p>",
            ),
            # Code blocks
            (
                "<pre><code>prometheus.remote_write</code></pre>",
                "<pre><code>prometheus.remote_write</code></pre>",
            ),
        ]
        for html, expected in cases:
            with self.subTest(html=html):
                self.assertEqual(render(html), expected)

    def test_outside_text(self) -> None:
        html = "<p><code>prometheus.remote_write</code></p>"
        self.assertEqual(render(html, "other"), html)


if __name__ == "__main__":
    unittest.main()

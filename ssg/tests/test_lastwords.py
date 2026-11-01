"""Tests for ssg.html.lastwords."""

import unittest

import lxml.html

from ssg.html import lastwords

W = '<span class="lf-last-words">'
S = '<span class="lf-last-space"> </span>'
H = '<span class="lf-print-ref" hidden>[13]</span>'


def render(html: str, cls: str = "lf-text") -> str:
    root = lxml.html.fromstring(f'<div class="{cls}">{html}</div>')
    lastwords.fix(root)
    output = lxml.html.tostring(root, encoding="unicode")
    return output[len(f'<div class="{cls}">') : -len("</div>")]


class TestLastWords(unittest.TestCase):
    def test_fix(self) -> None:
        cases = [
            ("<p>Hello the world.</p>", f"<p>Hello {W}the{S}world.</span></p>"),
            ("<p>two words</p>", f"<p>{W}two{S}words</span></p>"),
            ("<p>  two words\n</p>", f"<p>  {W}two{S}words\n</span></p>"),
            ("<p>alone</p>", "<p>alone</p>"),
            # Long last word: no join
            (
                "<p>Worry about browser compatibility.</p>",
                f"<p>Worry about browser {W}compatibility.</span></p>",
            ),
            # Second to last word inside an element
            (
                '<p>See <a href="x">the long link</a>.</p>',
                f'<p>See {W}<a href="x">the long{S}link</a>.</span></p>',
            ),
            (
                '<p>x <a href="y">deep <em>nest word</em></a> end</p>',
                f'<p>x {W}<a href="y">deep <em>nest word</em></a>{S}end</span></p>',
            ),
            (
                "<p>Run <code>ip link show</code></p>",
                f"<p>Run {W}<code>ip link{S}show</code></span></p>",
            ),
            # Space split in several places
            (
                "<p>foo <em>bar </em> baz</p>",
                f"<p>foo {W}<em>bar{S}</em>baz</span></p>",
            ),
            # Hidden text does not count in the length of the last word
            (
                f'<p>See <a href="x">the link</a>{H}.</p>',
                f'<p>See {W}<a href="x">the{S}link</a>{H}.</span></p>',
            ),
            # Not inline content
            ("<p>line<br>two words</p>", "<p>line<br>two words</p>"),
            (
                "<ul><li><p>in para</p></li></ul>",
                f"<ul><li><p>{W}in{S}para</span></p></li></ul>",
            ),
        ]
        for html, expected in cases:
            with self.subTest(html=html):
                self.assertEqual(render(html), expected)

    def test_outside_text(self) -> None:
        html = "<p>Hello the world.</p>"
        self.assertEqual(render(html, "other"), html)


if __name__ == "__main__":
    unittest.main()

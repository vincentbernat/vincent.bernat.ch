"""Tests for ssg.html.typography."""

import unittest

import lxml.etree
import lxml.html

from ssg.html import typography

H = '<span class="lf-print-ref" hidden>[13]</span>'


def render(html: str, cls: str = "lf-text", lang: str = "en") -> str:
    root = lxml.html.fromstring(
        f'<html lang="{lang}"><body><div class="{cls}">{html}</div></body></html>'
    )
    typography.fix(root)
    div = root.find(".//div")
    assert div is not None
    output = lxml.html.tostring(div, encoding="unicode")
    output = output[len(f'<div class="{cls}">') : -len("</div>")]
    # Make invisible characters visible
    return output.replace("\u00ad", "~").replace("\u00a0", "_").replace("\u202f", "^").replace("\u200b", "|")


class TestTypography(unittest.TestCase):
    def check(self, cases: list[tuple[str, str]], lang: str = "en") -> None:
        for html, expected in cases:
            with self.subTest(html=html):
                self.assertEqual(render(html, lang=lang), expected)

    def test_quotes(self) -> None:
        self.check(
            [
                (
                    "<div>He said \"yes\" and 'no'.</div>",
                    "<div>He said “yes” and ‘no’.</div>",
                ),
                ("<div>It's done...</div>", "<div>It’s done…</div>"),
                ("<div>In the '80s</div>", "<div>In the ’80s</div>"),
                ('<div>Is it "–"?</div>', "<div>Is it “–”?</div>"),
                ('<div>Yes—"no"</div>', "<div>Yes—“no”</div>"),
                ('<div><em>yes</em>"</div>', "<div><em>yes</em>”</div>"),
                (
                    '<ul><li>one</li><li>"two"</li></ul>',
                    "<ul><li>one</li><li>“two”</li></ul>",
                ),
                (
                    "<div><code>x</code>'s value</div>",
                    "<div><code>x</code>’s value</div>",
                ),
                (
                    '<div>Say "<em>yes</em>", now</div>',
                    "<div>Say “<em>yes</em>”, now</div>",
                ),
                (
                    '<div>Run <code>echo "a"</code></div>',
                    '<div>Run <code>echo "a"</code></div>',
                ),
            ]
        )

    def test_spaces(self) -> None:
        self.check(
            [
                (
                    "<div>« Oui ! » dit-il : non ; 50 %</div>",
                    "<div>«^Oui^!^» dit-il^: non^; 50^%</div>",
                ),
                ("<div>about 1 000 users</div>", "<div>about 1^000 users</div>"),
                ("<div>Use Python 3 now</div>", "<div>Use Python^3 now</div>"),
                ("<div>It is 10\u00a0km away</div>", "<div>It is 10^km away</div>"),
                ("<div>at 2.4 GHz, 3 Mb/s</div>", "<div>at 2.4^GHz, 3^Mb/s</div>"),
                ("<div>costs 5 € or 6\u00a0€</div>", "<div>costs 5^€ or 6^€</div>"),
                ("<div>It is 10 kmh</div>", "<div>It is 10 kmh</div>"),
                ("<div>step 1 A or 2 V</div>", "<div>step 1 A or 2 V</div>"),
            ]
        )

    def test_hyphens(self) -> None:
        self.check(
            [
                (
                    "<p>The hyphenation is nice to have.</p>",
                    "<p>The hy~phen~ation is nice_to_have.</p>",
                ),
                # Not in headings, code, URLs, acronyms and names
                ("<h2>Hyphenation</h2>", "<h2>Hyphenation</h2>"),
                (
                    "<pre><code>hyphenation</code></pre>",
                    "<pre><code>hyphenation</code></pre>",
                ),
                (
                    "<p>Read https://example.com/hyphenation first</p>",
                    "<p>Read https://example.com/hyphenation_first</p>",
                ),
                (
                    "<p>HAProxy and OpenBSD hyphenation rules</p>",
                    "<p>HAProxy and OpenBSD hy~phen~ation_rules</p>",
                ),
                # Except known names
                (
                    "<p>JavaScript on ThinkPads and here</p>",
                    "<p>Java~Script on Think~Pads_and_here</p>",
                ),
                # Only in paragraphs and lists
                ("<div>hyphenation rules</div>", "<div>hyphenation rules</div>"),
                (
                    "<ul><li>hyphenation rules</li></ul>",
                    "<ul><li>hy~phen~ation_rules</li></ul>",
                ),
                # Other languages
                (
                    '<p><span lang="fr">typographie</span> rules</p>',
                    '<p><span lang="fr">ty~po~gra~phie</span>_rules</p>',
                ),
                (
                    '<p><span lang="xx">hyphenation</span> rules</p>',
                    '<p><span lang="xx">hyphenation</span>_rules</p>',
                ),
            ]
        )
        self.check(
            [
                (
                    "<p>La typographie est importante.</p>",
                    "<p>La ty~po~gra~phie est im~portante.</p>",
                )
            ],
            lang="fr",
        )

    def test_last_line(self) -> None:
        self.check(
            [
                ("<p>Hello the universe.</p>", "<p>Hello the universe.</p>"),
                ("<p>Hello the world.</p>", "<p>Hello the_world.</p>"),
                ("<p>two words</p>", "<p>two_words</p>"),
                ("<p>  two words\n</p>", "<p>  two_words\n</p>"),
                ("<p>alone</p>", "<p>alone</p>"),
                ("<p>it is so.</p>", "<p>it_is_so.</p>"),
                # Long last word: only hyphens far from the end
                (
                    "<p>Worry about browser compatibility.</p>",
                    "<p>Worry about browser com~pat~ibility.</p>",
                ),
                # Last words inside an element
                (
                    '<p>See <a href="x">the long link</a>.</p>',
                    '<p>See <a href="x">the long_link</a>.</p>',
                ),
                (
                    '<p>x <a href="y">deep <em>nest word</em></a> end</p>',
                    '<p>x <a href="y">deep <em>nest_word</em></a>_end</p>',
                ),
                (
                    "<p>Run <code>ip link show</code></p>",
                    "<p>Run <code>ip link_show</code></p>",
                ),
                # Space split in several places
                ("<p>foo <em>bar </em> baz</p>", "<p>foo_<em>bar_</em>baz</p>"),
                # Hidden text does not count
                (
                    f'<p>See <a href="x">the link</a>{H}.</p>',
                    f'<p>See <a href="x">the_link</a>{H}.</p>',
                ),
                # No break in the last characters of code
                (
                    "<p>Use <code>foo.bar_bazqux</code></p>",
                    "<p>Use <code>foo.|bar_bazqux</code></p>",
                ),
                # Not inline content
                ("<p>line<br>two words</p>", "<p>line<br>two words</p>"),
                (
                    "<ul><li><p>in para</p></li></ul>",
                    "<ul><li><p>in_para</p></li></ul>",
                ),
            ]
        )

    def test_code_breaks(self) -> None:
        self.check(
            [
                (
                    "<div><code>prometheus.remote_write</code></div>",
                    "<div><code>prometheus.|remote_|write</code></div>",
                ),
                (
                    "<div><code>/etc/systemd/system</code></div>",
                    "<div><code>/etc/|systemd/|system</code></div>",
                ),
                (
                    "<div><code>2001:db8:a1::/64</code></div>",
                    "<div><code>2001:|db8:|a1::/64</code></div>",
                ),
                # Not before a space or a bracket
                (
                    "<div><code>ERROR: No DS</code></div>",
                    "<div><code>ERROR: No DS</code></div>",
                ),
                (
                    "<div><code>[::]:80 and [::]:443</code></div>",
                    "<div><code>[::]:|80 and [::]:|443</code></div>",
                ),
                # Numbers, short parts and repeated marks
                ("<div><code>1.2.3</code></div>", "<div><code>1.2.3</code></div>"),
                ("<div><code>a.b</code></div>", "<div><code>a.b</code></div>"),
                (
                    "<div><code>..foo..bar</code></div>",
                    "<div><code>..foo..|bar</code></div>",
                ),
                # Elements inside code
                (
                    "<div><code><span>discovery</span>.kubernetes_sd_configs</code></div>",
                    "<div><code><span>discovery</span>.kubernetes_|sd_|configs</code></div>",
                ),
                # Code blocks
                (
                    "<pre><code>prometheus.remote_write</code></pre>",
                    "<pre><code>prometheus.remote_write</code></pre>",
                ),
            ]
        )

    def test_outside_text(self) -> None:
        html = '<p>He said "yes" to <code>a.remote_write</code> hyphenation.</p>'
        self.assertEqual(render(html, "other"), html)

    def test_title(self) -> None:
        root = lxml.html.fromstring(
            '<html lang="en"><body><article><header><h1>The "hyphenation"'
            "</h1></header></article></body></html>"
        )
        typography.fix(root)
        h1 = root.find(".//h1")
        assert h1 is not None
        self.assertEqual(h1.text, "The “hyphenation”")

    def test_nested(self) -> None:
        html = '<div class="lf-text"><p>The "hyphenation" rules</p></div>'
        self.assertEqual(
            render(html), '<div class="lf-text"><p>The “hy~phen~ation”_rules</p></div>'
        )

    def test_feed(self) -> None:
        div = lxml.etree.fromstring(
            '<div xmlns="http://www.w3.org/1999/xhtml">'
            '<p>He said "hyphenation" : <code>a.b "c"</code></p></div>'
        )
        typography.punctuate(div)
        p = div[0]
        self.assertEqual(p.text, "He said “hyphenation”\u202f: ")
        self.assertEqual(p[0].text, 'a.b "c"')


if __name__ == "__main__":
    unittest.main()

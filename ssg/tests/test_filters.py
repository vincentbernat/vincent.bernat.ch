"""Tests for ssg.templates.filters."""

import unittest

from markupsafe import Markup

from ssg.templates.filters import capitalize, punctuate


class TestPunctuate(unittest.TestCase):
    def check(self, cases: list[tuple[str, str]], mark: str = ".") -> None:
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(punctuate(text, mark), expected)

    def test_plain(self) -> None:
        self.check(
            [
                ("", ""),
                ("Sound", "Sound."),
                ("Sound.", "Sound."),
                ("Why?", "Why?"),
                ("Yes!", "Yes!"),
                (
                    "If I Made Another Monkey Island…",
                    "If I Made Another Monkey Island…",
                ),
            ]
        )

    def test_quotes(self) -> None:
        self.check(
            [
                ("“Sound”", "“Sound.”"),
                ("“Why?”", "“Why?”"),
                ("“A ‘quoted’ word”", "“A ‘quoted’ word.”"),
                ("“‘Quoted’”", "“‘Quoted.’”"),
                ("“‘Why?’”", "“‘Why?’”"),
                ('"Sound"', '"Sound."'),
                ("« Son »", "« Son »."),
                ("« Pourquoi ? »", "« Pourquoi ? »"),
            ]
        )

    def test_html(self) -> None:
        self.check(
            [
                ("“<a href='x'>Sound</a>”", "“<a href='x'>Sound</a>.”"),
                ("“<a href='x'>Why?</a>”", "“<a href='x'>Why?</a>”"),
                ("“<a><em>Sound</em></a>”", "“<a><em>Sound</em></a>.”"),
                ("<em>Sound</em>", "<em>Sound</em>."),
            ]
        )

    def test_markdown(self) -> None:
        self.check(
            [
                (
                    "“[Sound](self://x){ .lf-title }”",
                    "“[Sound](self://x){ .lf-title }.”",
                ),
                ("“[Why?](self://x){ .lf-title }”", "“[Why?](self://x){ .lf-title }”"),
                ("“[Sound](https://x)”", "“[Sound](https://x).”"),
            ]
        )

    def test_mark(self) -> None:
        self.check(
            [
                ("“Sound”", "“Sound,”"),
                ("“Why?”", "“Why?”"),
                ("Sound", "Sound,"),
            ],
            mark=",",
        )

    def test_markup(self) -> None:
        result = punctuate(Markup("a &amp; b"))
        self.assertIsInstance(result, Markup)
        self.assertEqual(result, Markup("a &amp; b."))


class TestCapitalize(unittest.TestCase):
    def test_capitalize(self) -> None:
        for text, expected in [
            ("", ""),
            ("in French", "In French"),
            ("en français", "En français"),
            ("comics about HTTP", "Comics about HTTP"),
            ("Already", "Already"),
            ("éric", "Éric"),
        ]:
            with self.subTest(text=text):
                self.assertEqual(capitalize(text), expected)


if __name__ == "__main__":
    unittest.main()

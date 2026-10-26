"""Helpers for lxml trees."""

from __future__ import annotations

import functools
import re

import lxml.cssselect
import lxml.etree
import lxml.html

# Elements displayed inline. Other elements separate words.
INLINE_TAGS = frozenset({
    "a", "abbr", "acronym", "b", "bdo", "big", "button", "cite", "code",
    "dfn", "em", "i", "img", "input", "kbd", "label", "map", "object", "q",
    "samp", "script", "select", "small", "span", "strong", "sub", "sup",
    "textarea", "time", "tt", "var",
})  # fmt: skip

WHITESPACE = re.compile(r"[ \t\n\f\r\u200b]+")


@functools.cache
def compiled(selector: str) -> lxml.cssselect.CSSSelector:
    return lxml.cssselect.CSSSelector(selector, translator="html")


def select(root: lxml.etree._Element, selector: str) -> list[lxml.etree._Element]:
    """Elements matching a CSS selector, root included."""
    return compiled(selector)(root)


def namespace(el: lxml.etree._Element) -> str:
    """Namespace part of the tag name, with braces."""
    tag = str(el.tag)
    return tag[: tag.find("}") + 1]


def localname(el: lxml.etree._Element) -> str:
    """Tag name without namespace."""
    return str(el.tag).rpartition("}")[2]


def rename(el: lxml.etree._Element, name: str) -> None:
    """Change the tag name, keep the namespace."""
    el.tag = namespace(el) + name


def element(
    ref: lxml.etree._Element, name: str, attrib: dict[str, str] | None = None
) -> lxml.etree._Element:
    """Create an element of the same kind and namespace as ref."""
    el = ref.makeelement(name, attrib or {})
    el.tag = namespace(ref) + name
    return el


def classes(el: lxml.etree._Element) -> list[str]:
    return (el.get("class") or "").split()


def add_class(el: lxml.etree._Element, name: str) -> None:
    current = classes(el)
    if name not in current:
        el.set("class", " ".join(current + [name]))


def remove_class(el: lxml.etree._Element, name: str) -> None:
    el.set("class", " ".join(c for c in classes(el) if c != name))


def set_flag(el: lxml.etree._Element, name: str) -> None:
    """Set a boolean attribute. In HTML, it has no value. In XML, for feeds,
    its value is empty."""
    if isinstance(el, lxml.html.HtmlElement):
        el.set(name, None)
    else:
        el.set(name, "")


def remove(el: lxml.etree._Element) -> None:
    """Remove an element, keep the text after it."""
    parent = el.getparent()
    if parent is None:
        return
    if el.tail:
        previous = el.getprevious()
        if previous is None:
            parent.text = (parent.text or "") + el.tail
        else:
            previous.tail = (previous.tail or "") + el.tail
    parent.remove(el)


def text(el: lxml.etree._Element) -> str:
    """Text of an element, with spaces between blocks and no extra spaces."""
    parts: list[str] = []

    def walk(el: lxml.etree._Element) -> None:
        block = localname(el) not in INLINE_TAGS
        if block:
            parts.append(" ")
        parts.append(el.text or "")
        for child in el:
            if isinstance(child.tag, str):
                walk(child)
            parts.append(child.tail or "")
        if block:
            parts.append(" ")

    walk(el)
    return WHITESPACE.sub(" ", "".join(parts)).strip()

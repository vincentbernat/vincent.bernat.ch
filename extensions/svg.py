"""
SVG plugins
"""

import re
import lxml.etree
from hyde.plugin import Plugin

# Same as in root.css
SANS_STACK = (
    'Seravek, "Gill Sans Nova", "Source Sans Pro", source-sans-pro, '
    'Cantarell, Ubuntu, "DejaVu Sans", sans-serif'
)
# See https://github.com/system-fonts/modern-font-stacks#monospace-code
MONO_STACK = (
    "ui-monospace, 'Cascadia Code', 'Source Code Pro', Menlo, Consolas, "
    "'DejaVu Sans Mono', monospace"
)

SANS_TRIGGERS = {
    "sans-serif",
    "bitstream vera sans",
    "helvetica",
    "roboto",
    "roboto medium",
    "verdana",
    "source sans pro",
    "droid sans",
    "liberation sans",
}
MONO_TRIGGERS = {"monospace", "iosevka", "inconsolata"}

FONT_FAMILY_RE = re.compile(r"font-family\s*:\s*([^;}]+)")
INKSCAPE_RE = re.compile(
    r"\s*-inkscape-font-specification\s*:\s*[^;}]*;?", re.IGNORECASE
)
COLOR_SCHEME_RE = re.compile(r"\s*color-scheme\s*:\s*[^;}]*;?", re.IGNORECASE)
LIGHT_DARK_RE = re.compile(r"light-dark\s*\(", re.IGNORECASE)

# SVG presentation attributes that take a <color> value.
COLOR_ATTRS = frozenset(
    {
        "fill",
        "stroke",
        "color",
        "stop-color",
        "flood-color",
        "lighting-color",
        "solid-color",
        "viewport-fill",
    }
)


def flatten_light_dark(value):
    """Replace light-dark(A, B) calls with their first argument."""
    out = []
    pos = 0
    while True:
        match = LIGHT_DARK_RE.search(value, pos)
        if not match:
            out.append(value[pos:])
            return "".join(out)
        out.append(value[pos : match.start()])
        depth = 1
        comma = -1
        i = match.end()
        while i < len(value) and depth:
            c = value[i]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            elif c == "," and depth == 1 and comma < 0:
                comma = i
            i += 1
        if depth == 0 and comma >= 0:
            out.append(value[match.end() : comma].strip())
            pos = i
        else:
            out.append(value[match.start() : i])
            pos = i


def replacement_for(value):
    key = value.strip().strip("'\"").strip().lower()
    if key in SANS_TRIGGERS:
        return SANS_STACK
    if key in MONO_TRIGGERS:
        return MONO_STACK
    return None


def rewrite_css(css):
    """Rewrite font-family, drop -inkscape-font-specification and color-scheme,
    flatten light-dark()."""

    def sub(match):
        stack = replacement_for(match.group(1))
        return f"font-family:{stack}" if stack else match.group(0)

    css = INKSCAPE_RE.sub("", css)
    css = COLOR_SCHEME_RE.sub("", css)
    css = FONT_FAMILY_RE.sub(sub, css)
    return flatten_light_dark(css)


def localname(tag):
    """Local name of an element tag, or None for comments and PIs."""
    if not isinstance(tag, str):
        return None
    return tag.rsplit("}", 1)[-1]


def replace_attr(el, name):
    """Rewrite an attribute holding a font name list (font-family, face)."""
    value = el.get(name)
    if value:
        stack = replacement_for(value)
        if stack:
            el.set(name, stack)


class SVGFontsPlugin(Plugin):
    """Normalize font-family declarations in SVG files."""

    def text_resource_complete(self, resource, text):
        if resource.source_file.kind != "svg":
            return
        root = lxml.etree.fromstring(text.encode("utf-8"))

        # Remove draw.io/excalidraw original diagrams
        root.attrib.pop("content", None)
        for child in list(root):
            if localname(child.tag) == "metadata":
                root.remove(child)

        for el in root.iter():
            replace_attr(el, "font-family")
            if localname(el.tag) == "font":
                # Deprecated XHTML <font face="..."> inside <foreignObject>.
                replace_attr(el, "face")
            for name in COLOR_ATTRS.intersection(el.attrib):
                value = el.get(name)
                if "light-dark" in value.lower():
                    el.set(name, flatten_light_dark(value))
            style = el.get("style")
            if style:
                el.set("style", rewrite_css(style))
            if localname(el.tag) == "style" and el.text:
                el.text = rewrite_css(el.text)
        return lxml.etree.tostring(
            root.getroottree(), xml_declaration=True, encoding="UTF-8"
        ).decode("utf-8")

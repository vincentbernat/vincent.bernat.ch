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


def replacement_for(value):
    key = value.strip().strip("'\"").strip().lower()
    if key in SANS_TRIGGERS:
        return SANS_STACK
    if key in MONO_TRIGGERS:
        return MONO_STACK
    return None


def rewrite_css(css):
    """Rewrite font-family declarations and drop -inkscape-font-specification."""

    def sub(match):
        stack = replacement_for(match.group(1))
        return f"font-family:{stack}" if stack else match.group(0)

    return INKSCAPE_RE.sub("", FONT_FAMILY_RE.sub(sub, css))


def localname(tag):
    """Local name of an element tag, or None for comments and PIs."""
    if not isinstance(tag, str):
        return None
    return tag.rsplit("}", 1)[-1]


class SVGFontsPlugin(Plugin):
    """Normalize font-family declarations in SVG files."""

    def text_resource_complete(self, resource, text):
        if resource.source_file.kind != "svg":
            return
        root = lxml.etree.fromstring(text.encode("utf-8"))
        for el in root.iter():
            family = el.get("font-family")
            if family:
                stack = replacement_for(family)
                if stack:
                    el.set("font-family", stack)
            style = el.get("style")
            if style:
                el.set("style", rewrite_css(style))
            if localname(el.tag) == "style" and el.text:
                el.text = rewrite_css(el.text)
        return lxml.etree.tostring(
            root.getroottree(), xml_declaration=True, encoding="UTF-8"
        ).decode("utf-8")

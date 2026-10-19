"""Normalize fonts and colors in SVG files."""

import base64
import re
import tempfile
from pathlib import Path

import lxml.etree

from .. import deps
from ..tools import run

# An image cannot load a font from the network, so each file carries the fonts
# it needs, cut down to the characters it shows. Only regular is available.
FONTS = {
    "sans-serif": "Source Sans 3",
    "serif": "Literata",
    "monospace": "Iosevka",
}
# Environment variables with the font files. They are not compressed to make
# subsetting faster.
FONT_FILES = {
    "sans-serif": "SSG_SOURCE_SANS_FONT",
    "serif": "SSG_LITERATA_FONT",
    "monospace": "SSG_IOSEVKA_FONT",
}

SANS_TRIGGERS = {
    "sans-serif",
    "arial",
    "bitstream vera sans",
    "helvetica",
    "roboto",
    "roboto medium",
    "verdana",
    "source sans pro",
    "droid sans",
    "liberation sans",
    "linux biolinum o",
    "xkcd script",
}
SERIF_TRIGGERS = {
    "serif",
    "times",
    "times new roman",
    "georgia",
    "liberation serif",
    "nimbus roman",
    "dejavu serif",
    "droid serif",
    "noto serif",
    "adobe garamond pro",
    "itc new baskerville std",
}
MONO_TRIGGERS = {"monospace", "iosevka", "inconsolata"}

TRIGGERS = {
    "sans-serif": SANS_TRIGGERS,
    "serif": SERIF_TRIGGERS,
    "monospace": MONO_TRIGGERS,
}

# Elements whose text is not displayed
HIDDEN = frozenset({"style", "script", "metadata", "desc", "title"})

FONT_FAMILY_RE = re.compile(r"font-family\s*:\s*([^;}]+)")
FONT_FACE_RE = re.compile(r"(@font-face\s*\{[^}]*\})")
INKSCAPE_RE = re.compile(r"\s*-inkscape-font-specification\s*:\s*[^;}]*;?")
COLOR_SCHEME_RE = re.compile(r"\s*color-scheme\s*:\s*[^;}]*;?")
LIGHT_DARK_RE = re.compile(r"light-dark\s*\(")

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


def flatten_light_dark(value: str) -> str:
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


class Fonts:
    """Fonts of one file: the ones it carries itself and the ones we add."""

    def __init__(self, embedded: set[str]) -> None:
        self.embedded = embedded
        self.used: set[str] = set()

    def replace(self, value: str) -> str | None:
        """New value for a list of font names, or None to keep it."""
        for name in value.split(","):
            name = name.strip().strip("'\"").strip().lower()
            if name in self.embedded:
                return None
            for generic, triggers in TRIGGERS.items():
                if name in triggers:
                    self.used.add(generic)
                    return f'"{FONTS[generic]}", {generic}'
        raise ValueError(f"unknown font in SVG: {value}")


def rewrite_css(css: str, fonts: Fonts) -> str:
    """Rewrite font-family, drop -inkscape-font-specification and
    color-scheme, flatten light-dark()."""

    def sub(match: re.Match[str]) -> str:
        replacement = fonts.replace(match.group(1))
        return f"font-family:{replacement}" if replacement else match.group(0)

    css = INKSCAPE_RE.sub("", css)
    css = COLOR_SCHEME_RE.sub("", css)
    parts = FONT_FACE_RE.split(css)  # [ CSS, @font-face, CSS, @font-face, ..., CSS ]
    parts[::2] = [FONT_FAMILY_RE.sub(sub, part) for part in parts[::2]]
    parts[1::2] = [b if "data:" in b else "" for b in parts[1::2]]
    return flatten_light_dark("".join(parts))


def embedded_fonts(root: lxml.etree._Element) -> set[str]:
    """Font names embedded with @font-face."""
    names: set[str] = set()
    for el in root.iter():
        if localname(el.tag) != "style" or not el.text:
            continue
        for block in FONT_FACE_RE.findall(el.text):
            if "data:" not in block:
                continue
            for mo in FONT_FAMILY_RE.finditer(block):
                names.add(mo.group(1).strip().strip("'\"").strip().lower())
    return names


def displayed(root: lxml.etree._Element) -> str:
    """Characters displayed by the file."""
    found: set[str] = set()
    for el in root.iter():
        if el.text and localname(el.tag) not in HIDDEN:
            found.update(el.text)
        if el.tail:
            found.update(el.tail)
    return "".join(sorted(c for c in found if c.isprintable()))


def font_file(generic: str) -> Path:
    """The font to embed."""
    return Path(deps.getenv(FONT_FILES[generic]))


@deps.cache
def font_face(generic: str, characters: str) -> str:
    """A @font-face rule with the font cut down to these characters."""
    source = font_file(generic)
    deps.record_file(source)
    # Iosevka has no useful feature, the two others only need kerning.
    features = "" if generic == "monospace" else "kern"
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "font.woff2"
        run(
            "pyftsubset",
            source,
            f"--text={characters}",
            "--flavor=woff2",
            f"--output-file={target}",
            f"--layout-features={features}",
            "--no-hinting",
            "--desubroutinize",
        )
        data = base64.b64encode(target.read_bytes()).decode("ascii")
    return (
        f'@font-face{{font-family:"{FONTS[generic]}";'
        f"src:url(data:font/woff2;base64,{data})}}"
    )


def localname(tag: object) -> str | None:
    """Local name of an element tag, or None for comments and PIs."""
    if not isinstance(tag, str):
        return None
    return tag.rsplit("}", 1)[-1]


def replace_attr(el: lxml.etree._Element, name: str, fonts: Fonts) -> None:
    """Rewrite an attribute holding a font name list (font-family, face)."""
    value = el.get(name)
    if value:
        replacement = fonts.replace(value)
        if replacement:
            el.set(name, replacement)


def process(text: str) -> str:
    """Normalize fonts and colors in SVG files."""
    root = lxml.etree.fromstring(text.encode("utf-8"))

    # Remove draw.io/excalidraw original diagrams
    root.attrib.pop("content", None)
    for child in list(root):
        if localname(child.tag) == "metadata":
            root.remove(child)

    fonts = Fonts(embedded_fonts(root))
    for el in root.iter():
        replace_attr(el, "font-family", fonts)
        if localname(el.tag) == "font":
            # Deprecated XHTML <font face="..."> inside <foreignObject>.
            replace_attr(el, "face", fonts)
        for name in COLOR_ATTRS.intersection(el.attrib):
            value = el.attrib[name]
            if "light-dark" in value.lower():
                el.set(name, flatten_light_dark(value))
        style = el.get("style")
        if style:
            el.set("style", rewrite_css(style, fonts))
        if localname(el.tag) == "style" and el.text:
            el.text = rewrite_css(el.text, fonts)

    characters = displayed(root)
    if fonts.used and characters:
        namespace = lxml.etree.QName(root).namespace
        faces = lxml.etree.Element(f"{{{namespace}}}style" if namespace else "style")
        faces.text = "".join(
            font_face(generic, characters) for generic in sorted(fonts.used)
        )
        root.insert(0, faces)

    output = lxml.etree.tostring(
        root.getroottree(), xml_declaration=True, encoding="UTF-8"
    ).decode("utf-8")
    if "light-dark(" in output:
        raise ValueError("light-dark() remains in SVG")
    return output

"""Size of images and if they are opaque or interactive."""

from __future__ import annotations

import base64
import io
import json
import math
import re
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PIL import Image

from .. import deps
from ..tools import run

if TYPE_CHECKING:
    from ..model.resource import Resource
    from ..model.site import Site


def to_px(x: str) -> int:
    """Convert a size to pixels."""
    mo = re.match(r"(?P<size>\d+(?:\.\d*)?)(?P<unit>.*)", x)
    if not mo:
        raise ValueError(f"cannot convert {x} to pixel")
    unit = mo.group("unit")
    size = float(mo.group("size"))
    if unit in {"", "px"}:
        return int(size)
    if unit == "pt":
        return int(size * 4 / 3)
    raise ValueError(f"unknown unit {unit}")


def get(site: Site, image: Resource) -> dict[str, Any]:
    """Size of an image and if it is opaque or interactive."""
    path = site.raw(image.path.removeprefix("media/"))
    deps.record_file(path)
    return read(str(path), image.kind)


@deps.cache
def read(path: str, kind: str) -> dict[str, Any]:
    match kind:
        case "png" | "jpg" | "webp" | "gif":
            img = Image.open(path)
            if "P" in img.mode:
                colors = img.getcolors()
                if colors is None:
                    raise ValueError(f"{path}: too many colors for a palette")
                transparency = img.info.get("transparency", -1)
                if any(idx == transparency for _, idx in colors):
                    return {"size": img.size, "opaque": False}
            if "A" not in img.mode or img.getchannel("A").getextrema()[0] == 255:
                # Find a dominant color
                reduced = img.copy()
                reduced.thumbnail((150, 150))
                paletted = reduced.convert(
                    "P", palette=Image.Palette.ADAPTIVE, colors=8
                )
                palette = paletted.getpalette()
                colors = paletted.getcolors()
                index = max(colors)[1] if colors else None
                if palette is None or not isinstance(index, int):
                    raise ValueError(f"{path}: cannot reduce to 8 colors")
                dominant = palette[index * 3 : index * 3 + 3]
                # Create an image with the exact same ratio using this color
                gcd = math.gcd(*img.size)
                lqip = Image.new(
                    "P", (img.size[0] // gcd, img.size[1] // gcd), tuple(dominant)
                )
                buffer = io.BytesIO()
                lqip.save(buffer, "PNG", optimize=True, bits=1)
                encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
                return {
                    "size": img.size,
                    "opaque": True,
                    "lqip": f"data:image/png;base64,{encoded}",
                }
            return {"size": img.size, "opaque": False}
        case "svg":
            # drawio exports point to this page when text is not real text
            drawio = "https://www.drawio.com/doc/faq/svg-export-text-problems"
            ns = {"svg": "http://www.w3.org/2000/svg"}
            xlink_href = "{http://www.w3.org/1999/xlink}href"
            svg = ET.parse(path).getroot()
            interactive = svg.find(".//svg:script", ns) is not None or any(
                (link.get("href") or link.get(xlink_href)) != drawio
                for link in svg.iterfind(".//svg:a", ns)
            )
            return {
                "size": tuple(
                    (to_px(x) or None) if x else None
                    for x in (svg.attrib.get("width"), svg.attrib.get("height"))
                ),
                "opaque": False,
                "interactive": interactive,
            }
        case "m3u8":
            content = Path(path).read_text()
            w, h = max(
                (int(w), int(h))
                for w, h in re.findall(r"RESOLUTION=(\d+)x(\d+)(?:$|,)", content)
            )
            return {"size": (w, h), "opaque": True}
        case "mp4" | "ogv":
            output = run(
                "ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path
            )
            streams = json.loads(output)["streams"]
            track = next(t for t in streams if t["codec_type"] == "video")
            return {"size": (track["width"], track["height"]), "opaque": True}
        case "pdf":
            from pypdf import PdfReader

            with Path(path).open("rb") as f:
                pdf = PdfReader(f)
                box = pdf.pages[0].mediabox
                # PDF physical sizes may be skewed, notably for slides. Assume
                # width will be around 1000.
                ratio = Fraction(Fraction(box.width), Fraction(box.height))
                ratio = ratio.limit_denominator(100)
                width = 1000 // ratio.numerator * ratio.numerator
                height = 1000 // ratio.numerator * ratio.denominator
                return {"size": (width, height), "opaque": True}
    return {"size": (None, None), "opaque": True}

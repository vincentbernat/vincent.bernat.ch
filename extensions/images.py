"""
Contains classes to handle images related things.

# Requires PIL/Pillow
"""

import hashlib
import inspect
import os
import io
import base64
import math
import re
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
import lxml.etree
import lxml.html
import types
import subprocess
import json
from functools import cache, cached_property, partial
from fractions import Fraction
from typing import NamedTuple

from hyde.plugin import Plugin
from fswrap import File, Folder

from pyquery import PyQuery as pq
from PIL import Image
import diskcache
import skia
import langcodes
from PyPDF2 import PdfReader


class Thumb(NamedTuple):
    path: str
    width: int
    height: int


class ImageThumbnailsPlugin(Plugin):
    """Provide a thumb() method on each JPG/PNG image resource.

    Each image resource will get a `thumb()` function. This function
    can take the following keywords:
      - width (int)
      - height (int)

    The `thumb()` function will return a `Thumb` namedtuple with
    `path`, `width` and `height` attributes.

    Thumbnails are created in the same directory as their image.
    Only supports PNG and JPG.
    """

    def begin_site(self):
        config = self.site.config
        defaults = {"width": None, "height": 40, "prefix": "thumb_"}
        if hasattr(config, "thumbnails"):
            defaults.update(config.thumbnails)
        thumb_fn = partial(self._generate, defaults=defaults)
        for node in self.site.content.walk():
            for resource in node.resources:
                if resource.source_file.kind not in ("jpg", "png"):
                    continue
                resource.thumb = types.MethodType(thumb_fn, resource)

    @staticmethod
    def _generate(resource, defaults, width=None, height=None):
        if width is None and height is None:
            width, height = defaults["width"], defaults["height"]
        im = Image.open(resource.path)
        width = width or im.size[0] * height // im.size[1] + 1
        height = height or im.size[1] * width // im.size[0] + 1
        im.thumbnail((width, height), Image.Resampling.LANCZOS)
        path = os.path.join(
            os.path.dirname(resource.get_relative_deploy_path()),
            f"{defaults['prefix']}{resource.name}",
        )
        target = File(Folder(resource.site.config.deploy_root_path).child(path))
        target.parent.make()
        if resource.name.endswith(".jpg"):
            im.save(target.path, "JPEG", quality=100)
        else:
            im.save(target.path, "PNG")
        return Thumb(path, im.size[0], im.size[1])


class ImageFixerPlugin(Plugin):
    """Fix images in various ways:

    - add width/height attributes
    - make them responsive
    - turn them into object if they are interactive
    - turn them into video if they are video
    """

    def __init__(self, site):
        super().__init__(site)
        self.cache = {}

    def _topx(self, x):
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

    def _img_properties(self, image):
        """Get size for an image, and opacity: (w, h), o?."""
        # Prefer the deployed output: `#!python` resources render to their final
        # form (e.g. SVG) and are generated first (see PythonPlugin), so their
        # source isn't usable. Fall back to the source for not-yet-built files.
        path = self.site.config.deploy_root_path.child(image.relative_deploy_path)
        if not os.path.exists(path):
            path = image.path
        match image.source_file.kind:
            case "png" | "jpg" | "webp" | "gif":
                img = Image.open(path)
                if "P" in img.mode and any(
                    idx == img.info.get("transparency", -1)
                    for _, idx in img.getcolors()
                ):
                    return {"size": img.size, "opaque": False}
                if "A" not in img.mode or img.getextrema()[-1][0] == 255:
                    # Find a dominant color
                    reduced = img.copy()
                    reduced.thumbnail((150, 150))
                    paletted = reduced.convert(
                        "P", palette=Image.Palette.ADAPTIVE, colors=8
                    )
                    palette = paletted.getpalette()
                    color_counts = sorted(paletted.getcolors(), reverse=True)
                    palette_index = color_counts[0][1]
                    dominant = palette[palette_index * 3 : palette_index * 3 + 3]
                    # Create an image with the exact same ratio using this
                    # color
                    gcd = math.gcd(*img.size)
                    lqip = Image.new(
                        "P", (img.size[0] // gcd, img.size[1] // gcd), tuple(dominant)
                    )
                    output = io.BytesIO()
                    lqip.save(output, "PNG", optimize=True, bits=1)
                    encoded = base64.b64encode(output.getvalue()).decode("ascii")
                    return {
                        "size": img.size,
                        "opaque": True,
                        "lqip": f"data:image/png;base64,{encoded}",
                    }
                return {"size": img.size, "opaque": False}
            case "svg":
                svg = ET.parse(path).getroot()
                return {
                    "size": tuple(
                        (self._topx(x) or None) if x else None
                        for x in (svg.attrib.get("width"), svg.attrib.get("height"))
                    ),
                    "opaque": False,
                    "interactive": svg.find(".//{http://www.w3.org/2000/svg}script")
                    is not None,
                }
            case "m3u8":
                with open(path) as f:
                    w, h = max(
                        (int(w), int(h))
                        for w, h in re.findall(
                            r"RESOLUTION=(\d+)x(\d+)(?:$|,)", f.read()
                        )
                    )
                    return {"size": (w, h), "opaque": True}
            case "mp4" | "ogv":
                p = subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "quiet",
                        "-print_format",
                        "json",
                        "-show_streams",
                        path,
                    ],
                    check=True,
                    capture_output=True,
                    encoding="utf-8",
                )
                streams = json.loads(p.stdout)["streams"]
                track = next(t for t in streams if t["codec_type"] == "video")
                return {
                    "size": (track["width"], track["height"]),
                    "opaque": True,
                }
            case "pdf":
                with open(path, "rb") as f:
                    pdf = PdfReader(f)
                    box = pdf.pages[0].mediabox
                    # PDF physical sizes may be skewed, notably for
                    # slides. Assume width will be around 1000.
                    ratio = Fraction(Fraction(box.width), Fraction(box.height))
                    ratio = ratio.limit_denominator(100)
                    width = 1000 // ratio.numerator * ratio.numerator
                    height = 1000 // ratio.numerator * ratio.denominator
                    return {"size": (width, height), "opaque": True}
        return {"size": (None, None), "opaque": True}

    def _size(self, resource, src, width, height):
        """Determine size of an image (with cache)."""
        if src not in self.cache:
            if src.startswith(self.site.config.media_url):
                path = src.removeprefix(self.site.config.media_url).lstrip("/")
                path = self.site.config.media_root_path.child(path)
                image = self.site.content.resource_from_relative_deploy_path(path)
            elif src.startswith(self.site.media_url("videos/")[:-7]):
                path = src[len(self.site.media_url("videos/")) - 7 :]
                path = self.site.config.media_root_path.child(path)
                image = self.site.content.resource_from_relative_deploy_path(path)
            elif re.match(r"([a-z]+://|//).*", src):
                # Not a local link
                return None
            elif src.startswith("/"):
                # Absolute resource
                path = src.lstrip("/")
                image = self.site.content.resource_from_relative_deploy_path(path)
            else:
                # Relative resource
                path = resource.node.source_folder.child(src)
                image = self.site.content.resource_from_path(path)
            if image is None:
                self.logger.warning("[%s] has an unknown image %s", resource, src)
                return None
            self.cache[src] = self._img_properties(image)
            self.logger.debug("Image [%s] is %s", src, self.cache[src])
        dim = self.cache[src]["size"]
        new_width, new_height = dim
        if new_width is None or new_height is None:
            return None
        if width is not None:
            return (width, int(width) * new_height // new_width)
        elif height is not None:
            return (int(height) * new_width // new_height, height)
        return (new_width, new_height)

    def _resolve_css_em(self, expression):
        """Resolve a calc() expression against root.css variables to a rem
        value, delegating to @csstools/css-calc via node.

        """
        script = os.path.join(os.path.dirname(__file__), "css.js")
        css_path = os.path.join(
            str(self.site.config.media_root_path), "css", "root.css"
        )
        out = subprocess.run(
            ["node", script, "calc", css_path, expression],
            check=True,
            capture_output=True,
        ).stdout.decode("ascii")
        return float(re.match(r"[\d.]+", out.strip()).group(0))

    @cached_property
    def _page_width_px(self):
        """Compute the page width and breakpoint in pixels from CSS variables.

        The breakpoint matches the --lf-medium media query (--lf-vp-medium
        scaled by --lf-font-size). Below that viewport, the image fills 100vw;
        above, it caps at page width.

        """
        px_per_em = 16
        page_width = self._resolve_css_em(
            "calc(var(--lf-page-width) * var(--lf-font-size))"
        )
        breakpoint = self._resolve_css_em(
            "calc(var(--lf-vp-medium) * var(--lf-font-size))"
        )
        return (
            round(page_width * px_per_em),
            round(breakpoint * px_per_em),
        )

    def _resize(self, source, destination, factor):
        """Resize provided image from source to destination with the provided
        factor. Check for latest modification time.
        """
        if not source.startswith(self.site.config.media_url):
            raise ValueError(f"[{source}] cannot be resized")
        source = source.removeprefix(self.site.config.media_url).lstrip("/")
        source = self.site.config.media_root_path.child(source)
        source = self.site.content.resource_from_relative_deploy_path(source)
        if os.path.exists(os.path.join(os.path.dirname(source.path), destination)):
            # Image already provided with the correct size.
            return
        destination = os.path.join(
            os.path.dirname(
                self.site.config.deploy_root_path.child(source.relative_deploy_path)
            ),
            destination,
        )
        source = source.path
        if (
            os.path.exists(destination)
            and os.stat(source).st_mtime < os.stat(destination).st_mtime
        ):
            # Destination is more recent, assume size is correct
            return
        im = Image.open(source)
        im = im.resize(
            (int(im.width * factor), int(im.height * factor)), Image.Resampling.LANCZOS
        )
        File(destination).parent.make()
        if source.endswith(".jpg"):
            im.save(destination, "JPEG", quality=100)
        else:
            im.save(destination, "PNG")

    def text_resource_complete(self, resource, text):
        """
        When the resource is generated, search for img tag and fix them.
        """
        if resource.source_file.name == "atom.xml":
            root = lxml.etree.fromstring(text.encode("utf-8"))
            ns = {
                "atom": "http://www.w3.org/2005/Atom",
                "xhtml": "http://www.w3.org/1999/xhtml",
            }
            for c in root.findall("atom:entry/atom:content", ns):
                div = c.find("xhtml:div", ns)
                inner = "".join(
                    lxml.etree.tostring(child, encoding="unicode") for child in div
                )
                d = self._process(resource, f"<div>{inner}</div>")
                new_div = lxml.etree.fromstring(
                    f'<div xmlns="http://www.w3.org/1999/xhtml">{d.html()}</div>'
                )
                c.remove(div)
                c.append(new_div)
            return lxml.etree.tostring(
                root.getroottree(), xml_declaration=True, encoding="UTF-8"
            ).decode("utf-8")
        if resource.source_file.kind != "html":
            return

        d = self._process(resource, text)
        return "<!DOCTYPE html>\n" + d.outer_html()

    def _process(self, resource, text):
        d = pq(text, parser="html")
        for img in d.items("img"):
            width = img.attr.width
            height = img.attr.height
            src = img.attr.src
            src = urllib.parse.unquote(src)
            if src is None:
                self.logger.warning(
                    "[%s] has an img tag without src attribute", resource
                )
                continue
            if width is None or height is None:
                wh = self._size(resource, src, width, height)
                if wh is not None:
                    width, height = wh
                else:
                    width, height = None, None
            if width is not None:
                width, height = int(width), int(height)

            # Adapt width/height if this is a scaled image (something@2x.jpg)
            mo = re.match(r".*@(\d+)x\.[^.]*$", src)
            if mo and width is not None:
                factor = int(mo.group(1))
                width //= factor
                height //= factor
                versions = []
                for f in range(1, factor + 1):
                    if f == factor:
                        tname = src
                    else:
                        tname = src.replace(f"@{factor}x.", f"@{f}x.")
                        self._resize(src, os.path.basename(tname), float(f) / factor)
                    versions.append((tname, width * f))
                # Use weighted geometric mean of consecutive widths instead of
                # the real width: bias toward the smaller value so the browser
                # upgrades sooner to the bigger image.
                weight = 0.33  # lower values make the upgrade to the next size sooner
                srcset = []
                for i, (path, w) in enumerate(versions):
                    if i < len(versions) - 1:
                        w = round(w ** (1 - weight) * versions[i + 1][1] ** weight)
                    srcset.append(f"{path} {w}w")
                img.attr.src = versions[0][0]
                img.attr.srcset = ",".join(srcset)
                page_width_px, breakpoint_px = self._page_width_px
                # The image cannot display wider than its intrinsic width.
                page_width_px = min(page_width_px, width)
                breakpoint_px = min(breakpoint_px, width)
                img.attr.sizes = (
                    f"auto, (max-width: {breakpoint_px}px) 100vw, {page_width_px}px"
                )

            # Put new width/height
            if width is not None:
                img.attr.width = f"{width}"
                img.attr.height = f"{height}"

            # If image is an interactive SVG, turns into an object
            if src.endswith(".svg") and self.cache.get(src, {}).get("interactive"):
                img[0].tag = "object"
                img.attr("type", "image/svg+xml")
                img.attr("data", src)
                img.text(f"&#128444; {img.attr.alt or ''}")
                del img.attr.src
                del img.attr.alt

            # PDF files
            elif src.endswith(".pdf"):
                img[0].tag = "object"
                img.attr("type", "application/pdf")
                options = "&".join(
                    f"{k}={v}"
                    for k, v in {
                        "toolbar": 0,
                        "navpanes": 0,
                        "scrollbar": 0,
                        "view": "Fit",
                        # pdf.js in Firefox
                        "zoom": "page-fit",
                        "pagemode": "none",
                    }.items()
                )
                img.attr("data", f"{src}#{options}")
                fallback = pq("<a />")
                fallback.attr("href", src)
                fallback.text(img.attr.alt or "PDF")
                img.append(fallback)
                del img.attr.src
                del img.attr.alt

            # On-demand videos (should be in /videos)
            elif src.endswith(".m3u8"):
                id = os.path.splitext(os.path.basename(src))[0]
                img[0].tag = "video"
                img[0].set("controls", None)
                img.attr("preload", "none")
                img.attr("crossorigin", "anonymous")
                img.attr("poster", self.site.media_url(f"images/posters/{id}.jpg"))
                del img.attr.src
                del img.attr.alt
                # Add sources
                m3u8 = pq("<source>")
                m3u8.attr.src = self.site.media_url(f"videos/{id}.m3u8")
                m3u8.attr.type = "application/vnd.apple.mpegurl"
                img.append(m3u8)
                progressive = pq("<source>")
                progressive.attr.src = self.site.media_url(
                    f"videos/{id}/progressive.mp4"
                )
                progressive.attr.type = 'video/mp4; codecs="mp4a.40.2,avc1.4d401f"'
                img.append(progressive)
                vtts = [
                    v
                    for v in self.site.content.node_from_relative_path(
                        "media/videos"
                    ).walk_resources()
                    if v.name.endswith(".vtt") and v.name.startswith(f"{id}.")
                ]
                # Add chapters track if any
                for vtt in vtts:
                    if vtt.name != f"{id}.chapters.vtt":
                        continue
                    track = pq("<track>")
                    track.attr.src = self.site.media_url(vtt.relative_path[6:])
                    track.attr.kind = "chapters"
                    track.attr.label = resource.meta.l10n.chapters
                    img.append(track)
                # Add subtitle tracks if any
                for vtt in vtts:
                    code = vtt.name[len(id) + 1 : -4]
                    if code == "chapters":
                        continue
                    track = pq("<track>")
                    track.attr.src = self.site.media_url(vtt.relative_path[6:])
                    track.attr.kind = "subtitles"
                    track.attr.srclang = code
                    if resource.meta.language == code:
                        track[0].set("default", None)
                    if "-" not in code:
                        track.attr.label = langcodes.get(code).autonym()
                    else:
                        details = langcodes.get(code).describe(code)
                        lang = details["language"]
                        del details["language"]
                        track.attr.label = f"{lang} ({', '.join(details.values())})"
                    img.append(track)

            # If image is a video not in /videos turn into a simple
            # video tag like an animated GIF.
            elif src.endswith((".mp4", ".ogv")):
                img[0].tag = "video"
                for attr in "muted loop autoplay playsinline controls".split():
                    img[0].set(attr, None)
                del img.attr.alt

            # Lazy load
            if img[0].tag == "img" and width:
                lftext = img.parents(".lf-text")
                if lftext:
                    parents = img.parents()
                    rootEl = pq(parents[parents.index(lftext[0]) + 1])
                    if len(rootEl.prev_all()) > 3:
                        img.attr.loading = "lazy"
                    img.attr.decoding = "async"

            # If image is contained in a paragraph, enclose into a
            # responsive structure.
            parent = None
            parents = [p.tag for p in img.parents()]
            if parents[-1] == "p":
                parent = img.parent()
            elif parents[-2:] == ["p", "a"]:
                parent = img.parent().parent()
            if parent and parent.contents().length == 1:
                img.addClass("lf-media")
                inner = pq("<span />")
                outer = pq("<div />")
                inner.addClass("lf-media-inner")
                outer.addClass("lf-media-outer")
                if width is not None:
                    inner.css.padding_bottom = f"{height * 100.0 / width:.3f}%"
                    outer.css.width = f"{width}px"
                outer.append(inner)

                # Check opacity
                if src in self.cache:
                    opaque = self.cache[src]["opaque"]
                    if opaque:
                        img.addClass("lf-opaque")
                        lqip = self.cache[src].get("lqip")
                        if lqip is not None:
                            img.css("background-image", f"url({lqip})")

                # If we have a title, also enclose in a figure
                figure = pq("<figure />")
                figure.addClass("lf-fullbleed")
                if img.attr.title:
                    figcaption = pq("<figcaption />")
                    figcaption.html(img.attr.title)
                    del img.attr.title
                    figure.append(outer)
                    figure.append(figcaption)
                else:
                    figure.append(outer)

                # Put image in inner tag
                if img.parent()[0].tag == "a":
                    inner.append(img.parent())
                else:
                    inner.append(img)
                # Replace parent with our enclosure
                parent.replace_with(lxml.html.tostring(figure[0], encoding="unicode"))

        return d


class CoverImagePlugin(Plugin):
    """Generate OG cover images (1200x630) for blog articles.

    Each blog article resource gets a cover_image() method that returns the
    media-relative path of its cover. The covers themselves are generated in
    begin_text_resource() for every registered resource.

    At some point, we should use self.site_content.add_resource to register the
    image as a resource (and add the original cover to .depends).
    """

    WIDTH = 1200
    HEIGHT = 630
    BG_COLOR = (255, 249, 240)  # #fff9f0
    AUTHOR_COLOR = (100, 100, 100)
    icon = None
    title_font = None
    author_font = None
    _cache = None
    _self_hash = None

    def begin_site(self):
        media_path = str(self.site.config.media_root_path)
        icon_path = os.path.join(media_path, "images", "favicon.png")
        CoverImagePlugin.icon = (
            Image.open(icon_path)
            .convert("RGBA")
            .resize((128, 128), Image.Resampling.NEAREST)
        )
        typeface = skia.Typeface.MakeFromName(
            "Noto Sans Display",
            skia.FontStyle(
                600, skia.FontStyle.kNormal_Width, skia.FontStyle.kUpright_Slant
            ),
        )
        CoverImagePlugin.title_font = skia.Font(typeface, 64)
        CoverImagePlugin.author_font = skia.Font(typeface, 32)

        # Disk cache, invalidated when CoverImagePlugin's source changes
        CoverImagePlugin._self_hash = hashlib.sha256(
            inspect.getsource(CoverImagePlugin).encode("utf-8")
        ).hexdigest()
        cache_dir = os.path.join(str(self.site.sitepath), ".cache", "covers")
        CoverImagePlugin._cache = diskcache.Cache(cache_dir, eviction_policy="none")
        CoverImagePlugin._cache.expire()

        self.covers = []
        for node in self.site.content.walk():
            for resource in node.resources:
                if resource.source_file.kind != "html":
                    continue
                if not resource.meta.title:
                    continue
                self.logger.debug("Adding cover_image function to [%s]", resource)
                resource.cover_image = types.MethodType(
                    CoverImagePlugin.cover_path, resource
                )
                self.covers.append(resource)

    def begin_text_resource(self, resource, text):
        """Generate the cover for a registered resource before it is rendered."""
        if resource in self.covers:
            self.generate(resource)

    @staticmethod
    def cover_path(resource, plugin=None):
        """Return the media-relative path of this article's cover image."""
        rdp = resource.relative_deploy_path
        return "images/covers/" + os.path.splitext(rdp)[0] + ".jpg"

    @staticmethod
    def _render_text(text, font, color):
        """Render text to a PIL RGBA image using skia."""
        width = math.ceil(font.measureText(text)) + 2
        metrics = font.getMetrics()
        ascent = math.ceil(-metrics.fAscent)
        descent = math.ceil(metrics.fDescent)
        height = ascent + descent
        if width <= 0 or height <= 0:
            return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

        surface = skia.Surface(width, height)
        canvas = surface.getCanvas()
        canvas.clear(skia.ColorTRANSPARENT)
        r, g, b = color
        paint = skia.Paint(AntiAlias=True)
        paint.setColor(skia.Color(r, g, b, 255))
        canvas.drawString(text, 0, ascent, font, paint)

        sk_img = surface.makeImageSnapshot()
        info = skia.ImageInfo.Make(
            width,
            height,
            skia.ColorType.kRGBA_8888_ColorType,
            skia.AlphaType.kUnpremul_AlphaType,
        )
        data = bytearray(width * height * 4)
        sk_img.readPixels(info, data, width * 4)
        return Image.frombytes("RGBA", (width, height), bytes(data))

    @staticmethod
    def _load_cover(cover_path, width):
        """Load a cover image (SVG or raster) and return as RGBA."""
        if cover_path.endswith(".svg"):
            p = subprocess.run(
                [
                    "resvg",
                    "--quiet",
                    "--font-family",
                    "Liberation Sans",
                    "--sans-serif-family",
                    "Liberation Sans",
                    "--serif-family",
                    "Liberation Serif",
                    "--monospace-family",
                    "Liberation Mono",
                    "--width",
                    str(width * 2),
                    cover_path,
                    "-c",
                ],
                check=True,
                capture_output=True,
            )
            return Image.open(io.BytesIO(p.stdout)).convert("RGBA")
        return Image.open(cover_path).convert("RGBA")

    @staticmethod
    @cache
    def _render_author(author, color):
        """Return a cached RGBA image of the author text."""
        return CoverImagePlugin._render_text(
            author, CoverImagePlugin.author_font, color
        )

    @staticmethod
    def _wrap_text(text, font, max_width):
        """Word-wrap text to fit within max_width, then balance line widths."""
        words = text.split()
        if not words:
            return []

        def line_width(s):
            return font.measureText(s)

        # Greedy wrap to determine number of lines
        lines = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            if line_width(test) <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)

        n = len(lines)
        if n <= 1:
            return lines

        # Balance: try to minimize max line width across n lines
        # Binary search for the smallest target width that fits in n lines
        lo, hi = max(line_width(w) for w in words), max_width
        while lo < hi:
            mid = (lo + hi) // 2
            # Try wrapping with mid as target width
            trial = []
            cur = ""
            for word in words:
                test = f"{cur} {word}".strip()
                if line_width(test) <= mid:
                    cur = test
                else:
                    if cur:
                        trial.append(cur)
                    cur = word
            if cur:
                trial.append(cur)
            if len(trial) <= n:
                hi = mid
            else:
                lo = mid + 1

        # Wrap with the balanced width
        lines = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            if line_width(test) <= hi:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    @staticmethod
    def generate(resource):
        """Generate a 1200x630 OG cover image for this article."""
        cls = CoverImagePlugin
        W, H = cls.WIDTH, cls.HEIGHT

        typeface = cls.title_font.getTypeface()
        title = "".join(
            ch
            for ch in resource.meta.title.split(" | ", 1)[0]
            if unicodedata.category(ch) != "Cf"
            and (typeface.unicharToGlyph(ord(ch)) != 0 or ch == " ")
        )
        has_cover = hasattr(resource.meta, "cover") and resource.meta.cover

        # Output path: media/images/covers/{relative_deploy_path}.jpg
        media_rel = cls.cover_path(resource)
        output_path = os.path.join(
            str(resource.site.config.deploy_root_path), "media", media_rel
        )

        # Resolve the cover.
        cover_path = None
        if has_cover:
            cover_path = os.path.join(
                str(resource.site.config.deploy_root_path),
                "media",
                "images",
                resource.meta.cover,
            )
            if not os.path.exists(cover_path):
                cover_path = os.path.join(
                    str(resource.site.config.media_root_path),
                    "images",
                    resource.meta.cover,
                )

        # Check disk cache
        cover_hash = ""
        if has_cover:
            with open(cover_path, "rb") as f:
                cover_hash = hashlib.file_digest(f, "sha256").hexdigest()
        cache_key = (title, resource.meta.author, cover_hash, cls._self_hash)
        cached = cls._cache.get(cache_key, read=True)
        if cached is not None:
            File(output_path).parent.make()
            with open(output_path, "wb") as f:
                f.write(cached.read())
            return media_rel

        font = cls.title_font
        line_height = int(font.getSize() * 1.2)
        margin = 40
        icon_w, icon_h = cls.icon.size

        if has_cover:
            # Layout: icon left, title + author right, at bottom
            gap = 20
            text_x = margin + icon_w + gap
            max_width = W - text_x - margin
            lines = cls._wrap_text(title, font, max_width)

            # Author line dimensions
            author_img = cls._render_author(resource.meta.author, cls.AUTHOR_COLOR)
            author_gap = 8

            # Text block = title lines + author
            text_block_h = len(lines) * line_height + author_gap + author_img.height
            block_h = max(icon_h, text_block_h)

            # Position block at bottom
            bottom_margin = 40
            block_y = H - bottom_margin - block_h

            # Load cover and crop to fill 1200x630
            cover = cls._load_cover(cover_path, W)
            target_ratio = W / H
            cover_ratio = cover.width / cover.height
            if cover_ratio > target_ratio:
                new_w = int(cover.height * target_ratio)
                left = (cover.width - new_w) // 2
                cover = cover.crop((left, 0, left + new_w, cover.height))
            else:
                new_h = int(cover.width / target_ratio)
                top = (cover.height - new_h) // 2
                cover = cover.crop((0, top, cover.width, top + new_h))
            cover = cover.resize((W, H), Image.Resampling.LANCZOS)
            img = Image.new("RGB", (W, H), cls.BG_COLOR)
            img.paste(cover, (0, 0), cover)

            # Gradient: start depends on block position
            bg = cls.BG_COLOR
            gradient_end = block_y
            gradient_start = max(0, gradient_end - int(H * 0.35))
            overlay = Image.new("RGBA", (W, H), (*bg, 0))
            for y in range(gradient_start, H):
                if y < gradient_end:
                    alpha = int(
                        255 * (y - gradient_start) / (gradient_end - gradient_start)
                    )
                else:
                    alpha = 255
                row = Image.new("RGBA", (W, 1), (*bg, alpha))
                overlay.paste(row, (0, y))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

            # Icon vertically centered with text block
            icon_y = block_y + (block_h - icon_h) // 2
            img.paste(cls.icon, (margin, icon_y), cls.icon)

            # Title left-aligned, vertically centered in block
            text_top = block_y + (block_h - text_block_h) // 2
            y = text_top
            for line in lines:
                line_img = cls._render_text(line, font, (0, 0, 0))
                img.paste(line_img, (text_x, int(y)), line_img)
                y += line_height

            # Author below title
            y += author_gap
            img.paste(author_img, (text_x, int(y)), author_img)
        else:
            # Without cover
            max_width = W - 120
            lines = cls._wrap_text(title, font, max_width)
            total_title_height = len(lines) * line_height

            img = Image.new("RGB", (W, H), cls.BG_COLOR)

            # Title (almost) centered
            y = (H - total_title_height + line_height) / 2
            for line in lines:
                line_img = cls._render_text(line, font, (0, 0, 0))
                x = (W - line_img.width) / 2
                img.paste(line_img, (int(x), int(y)), line_img)
                y += line_height

            # Branding: icon + author in upper left
            author_img = cls._render_author(
                resource.meta.author or "???", cls.AUTHOR_COLOR
            )
            img.paste(cls.icon, (margin, margin), cls.icon)
            author_y = margin + (icon_h - author_img.height) // 2
            img.paste(
                author_img,
                (margin + icon_w + margin, author_y),
                author_img,
            )

        # Save and cache
        File(output_path).parent.make()
        img.save(output_path, "JPEG", quality=100)
        with open(output_path, "rb") as f:
            cls._cache.set(cache_key, f, read=True, expire=30 * 86400)

        return media_rel

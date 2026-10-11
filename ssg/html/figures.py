"""Images: sizes, responsive versions, videos, PDF and interactive SVG."""

from __future__ import annotations

import os
import re
import sys
import urllib.parse
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import langcodes
import lxml.html
from pyquery import PyQuery as pq

from ..images import properties, scales
from ..media import css

if TYPE_CHECKING:
    from ..model.resource import Resource
    from ..model.site import Site


def resolve(site: Site, resource: Resource, src: str) -> Resource | None:
    """Find the resource for an image source."""
    media_url = site.mode.media_url
    cdn = [(prefix, url) for prefix, url in site.mode.cdn if src.startswith(url)]
    if src.startswith(media_url):
        path = "media/" + src.removeprefix(media_url).lstrip("/")
    elif cdn:
        prefix, url = cdn[0]
        path = "media/" + prefix + src.removeprefix(url)
    elif re.match(r"([a-z]+://|//).*", src):
        return None
    elif src.startswith("/"):
        path = src.lstrip("/")
    else:
        path = os.path.join(resource.node.path, src)
    image = site.resource(path)
    if image is None:
        print(f"[{resource}] has an unknown image {src}", file=sys.stderr)
    return image


def size(
    props: Mapping[str, Any] | None, width: str | None, height: str | None
) -> tuple[int, int] | None:
    """Compute the size of an image, scaled to the provided width or height."""
    if props is None:
        return None
    new_width, new_height = props["size"]
    if new_width is None or new_height is None:
        return None
    if width is not None:
        return (int(width), int(width) * new_height // new_width)
    elif height is not None:
        return (int(height) * new_width // new_height, int(height))
    return (new_width, new_height)


def fix(site: Site, resource: Resource, d: Any) -> None:
    """Add width/height to images, make them responsive, turn them into
    objects if they are interactive, into videos if they are videos."""
    for img in d.items("img"):
        width = img.attr.width
        height = img.attr.height
        src = urllib.parse.unquote(img.attr.src)
        props = None
        if width is None or height is None:
            image = resolve(site, resource, src)
            if image is not None:
                props = properties.get(site, image)
            wh = size(props, width, height)
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
            paths = scales.smaller(src) + [src]
            versions = [(path, width * (i + 1)) for i, path in enumerate(paths)]
            # Use weighted geometric mean of consecutive widths instead of the
            # real width: bias toward the smaller value so the browser
            # upgrades sooner to the bigger image.
            weight = 0.33  # lower values make the upgrade to the next size sooner
            srcset = []
            for i, (path, w) in enumerate(versions):
                if i < len(versions) - 1:
                    w = round(w ** (1 - weight) * versions[i + 1][1] ** weight)
                srcset.append(f"{path} {w}w")
            img.attr.src = versions[0][0]
            img.attr.srcset = ",".join(srcset)
            page_width_px, breakpoint_px = css.page_width()
            # The image cannot display wider than its intrinsic width.
            page_width_px = min(page_width_px, width)
            breakpoint_px = min(breakpoint_px, width)
            img.attr.sizes = (
                f"auto, (max-width: {breakpoint_px}px) 100vw, {page_width_px}px"
            )

        if width is not None:
            img.attr.width = f"{width}"
            img.attr.height = f"{height}"

        # Interactive SVG are turned into objects
        if src.endswith(".svg") and props and props.get("interactive"):
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
            video(site, resource, img, src)

        # Videos not in /videos are like an animated GIF
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
                root = pq(parents[parents.index(lftext[0]) + 1])
                if len(root.prev_all()) > 3:
                    img.attr.loading = "lazy"
                img.attr.decoding = "async"

        # If image is contained in a paragraph, enclose into a responsive
        # structure.
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

            if props and props["opaque"]:
                img.addClass("lf-opaque")
                lqip = props.get("lqip")
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


def video(site: Site, resource: Resource, img: Any, src: str) -> None:
    id = os.path.splitext(os.path.basename(src))[0]
    img[0].tag = "video"
    img[0].set("controls", None)
    img.attr("preload", "none")
    img.attr("crossorigin", "anonymous")
    img.attr("poster", site.media_url(f"images/posters/{id}.jpg"))
    del img.attr.src
    del img.attr.alt
    m3u8 = pq("<source>")
    m3u8.attr.src = site.media_url(f"videos/{id}.m3u8")
    m3u8.attr.type = "application/vnd.apple.mpegurl"
    img.append(m3u8)
    progressive = pq("<source>")
    progressive.attr.src = site.media_url(f"videos/{id}/progressive.mp4")
    progressive.attr.type = 'video/mp4; codecs="mp4a.40.2,avc1.4d401f"'
    img.append(progressive)
    vtts = site.tracks(id)
    # Chapters
    for vtt in vtts:
        if vtt.name != f"{id}.chapters.vtt":
            continue
        track = pq("<track>")
        track.attr.src = site.media_url(vtt.path[6:])
        track.attr.kind = "chapters"
        track.attr.label = resource.meta.l10n.chapters
        img.append(track)
    # Subtitles
    for vtt in vtts:
        code = vtt.name[len(id) + 1 : -4]
        if code == "chapters":
            continue
        track = pq("<track>")
        track.attr.src = site.media_url(vtt.path[6:])
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

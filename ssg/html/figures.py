"""Images: sizes, responsive versions, videos, PDF and interactive SVG."""

from __future__ import annotations

import posixpath
import re
import sys
import urllib.parse
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

import lxml.etree
import lxml.html
lazy import langcodes

from ..images import properties, scales
from ..media import css
from .dom import add_class, classes, element, localname, rename

if TYPE_CHECKING:
    from ..model.resource import Resource
    from ..model.site import Site


def set_flag(el: lxml.etree._Element, name: str) -> None:
    """Set a boolean attribute. In HTML, it has no value. In XML, for feeds,
    its value is empty."""
    if isinstance(el, lxml.html.HtmlElement):
        el.set(name, None)
    else:
        el.set(name, "")


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
        path = posixpath.join(resource.node.path, src)
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


def caption(ref: lxml.etree._Element, html: str) -> lxml.etree._Element:
    """Create a figcaption from an HTML string."""
    figcaption = lxml.html.fragment_fromstring(html, create_parent="figcaption")
    if isinstance(ref, lxml.html.HtmlElement):
        return figcaption
    # In feeds, use XML elements in the XHTML namespace
    lxml.html.html_to_xhtml(figcaption)
    return lxml.etree.fromstring(lxml.etree.tostring(figcaption))


def fix(site: Site, resource: Resource, root: lxml.etree._Element) -> None:
    """Add width/height to images, make them responsive, turn them into
    objects if they are interactive, into videos if they are videos."""
    for img in list(root.iter("{*}img")):
        width_attr = img.get("width")
        height_attr = img.get("height")
        src = urllib.parse.unquote(img.get("src", ""))
        props = None
        dims: tuple[int, int] | None
        if width_attr is None or height_attr is None:
            image = resolve(site, resource, src)
            if image is not None:
                props = properties.get(site, image)
            dims = size(props, width_attr, height_attr)
        else:
            dims = (int(width_attr), int(height_attr))

        # Adapt width/height if this is a scaled image (something@2x.jpg)
        mo = re.match(r".*@(\d+)x\.[^.]*$", src)
        if mo and dims is not None:
            factor = int(mo.group(1))
            width, height = dims[0] // factor, dims[1] // factor
            dims = (width, height)
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
            img.set("src", versions[0][0])
            img.set("srcset", ",".join(srcset))
            page_width_px, breakpoint_px = css.page_width()
            # The image cannot display wider than its intrinsic width.
            page_width_px = min(page_width_px, width)
            breakpoint_px = min(breakpoint_px, width)
            img.set(
                "sizes",
                f"auto, (max-width: {breakpoint_px}px) 100vw, {page_width_px}px",
            )

        if dims is not None:
            img.set("width", f"{dims[0]}")
            img.set("height", f"{dims[1]}")

        # Interactive SVG are turned into objects
        if src.endswith(".svg") and props and props.get("interactive"):
            rename(img, "object")
            img.set("type", "image/svg+xml")
            img.set("data", src)
            img.text = f"\U0001f5bc {img.get('alt') or ''}"
            img.attrib.pop("src", None)
            img.attrib.pop("alt", None)

        # PDF files
        elif src.endswith(".pdf"):
            rename(img, "object")
            img.set("type", "application/pdf")
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
            img.set("data", f"{src}#{options}")
            fallback = element(img, "a", {"href": src})
            fallback.text = img.get("alt") or "PDF"
            img.append(fallback)
            img.attrib.pop("src", None)
            img.attrib.pop("alt", None)

        # On-demand videos (should be in /videos)
        elif src.endswith(".m3u8"):
            video(site, resource, img, src)

        # Videos not in /videos are like an animated GIF
        elif src.endswith((".mp4", ".ogv")):
            rename(img, "video")
            for attr in ["muted", "loop", "autoplay", "playsinline", "controls"]:
                set_flag(img, attr)
            img.attrib.pop("alt", None)

        # Lazy load
        if localname(img) == "img" and dims and dims[0]:
            # Position in the outermost .lf-text
            top = None
            child = img
            for ancestor in img.iterancestors():
                if "lf-text" in classes(ancestor):
                    top = child
                child = ancestor
            if top is not None:
                if len(list(top.itersiblings(preceding=True))) > 3:
                    img.set("loading", "lazy")
                img.set("decoding", "async")

        # If image is contained in a paragraph, enclose into a responsive
        # structure.
        parent = img.getparent()
        if parent is not None and localname(parent) == "a":
            parent = parent.getparent()
        if (
            parent is not None
            and localname(parent) == "p"
            and len(parent.xpath("child::text()|child::*")) == 1
        ):
            add_class(img, "lf-media")
            inner = element(img, "span", {"class": "lf-media-inner"})
            outer = element(img, "div", {"class": "lf-media-outer"})
            if dims is not None:
                width, height = dims
                inner.set("style", f"padding-bottom: {height * 100.0 / width:.3f}%")
                outer.set("style", f"width: {width}px")
            outer.append(inner)

            if props and props["opaque"]:
                add_class(img, "lf-opaque")
                lqip = props.get("lqip")
                if lqip is not None:
                    style = img.get("style")
                    background = f"background-image: url({lqip})"
                    img.set("style", f"{style}; {background}" if style else background)

            # If we have a title, also enclose in a figure
            figure = element(img, "figure", {"class": "lf-fullbleed"})
            figure.append(outer)
            title = img.attrib.pop("title", None)
            if title:
                figure.append(caption(img, title))

            # Put image in inner tag
            link = img.getparent()
            inner.append(link if link is not None and link is not parent else img)
            # Replace parent with our enclosure
            figure.tail = parent.tail
            grandparent = parent.getparent()
            if grandparent is not None:
                grandparent.replace(parent, figure)


def video(site: Site, resource: Resource, img: lxml.etree._Element, src: str) -> None:
    id = PurePosixPath(src).stem
    rename(img, "video")
    set_flag(img, "controls")
    img.set("preload", "none")
    img.set("crossorigin", "anonymous")
    img.set("poster", site.media_url(f"images/posters/{id}.jpg"))
    img.attrib.pop("src", None)
    img.attrib.pop("alt", None)
    m3u8 = element(img, "source")
    m3u8.set("src", site.media_url(f"videos/{id}.m3u8"))
    m3u8.set("type", "application/vnd.apple.mpegurl")
    img.append(m3u8)
    progressive = element(img, "source")
    progressive.set("src", site.media_url(f"videos/{id}/progressive.mp4"))
    progressive.set("type", 'video/mp4; codecs="mp4a.40.2,avc1.4d401f"')
    img.append(progressive)
    vtts = site.tracks(id)
    # Chapters
    for vtt in vtts:
        if vtt.name != f"{id}.chapters.vtt":
            continue
        track = element(img, "track")
        track.set("src", site.media_url(vtt.path[6:]))
        track.set("kind", "chapters")
        track.set("label", resource.meta.l10n.chapters)
        img.append(track)
    # Subtitles
    for vtt in vtts:
        code = vtt.name[len(id) + 1 : -4]
        if code == "chapters":
            continue
        track = element(img, "track")
        track.set("src", site.media_url(vtt.path[6:]))
        track.set("kind", "subtitles")
        track.set("srclang", code)
        if resource.meta.language == code:
            set_flag(track, "default")
        if "-" not in code:
            track.set("label", langcodes.get(code).autonym())
        else:
            details = langcodes.get(code).describe(code)
            lang = details["language"]
            del details["language"]
            track.set("label", f"{lang} ({', '.join(details.values())})")
        img.append(track)

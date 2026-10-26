"""Hashed names for media files."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import lxml.etree

from .. import deps

if TYPE_CHECKING:
    from ..model.site import Site

ATTRIBUTE = re.compile(r"(data-|)[a-z]*")


def rewrite(site: Site, root: lxml.etree._Element) -> None:
    """Use hashed names for media files. Add integrity attributes for
    scripts, stylesheets and fonts."""
    media = site.mode.media_url
    recent = deps.recent_assets(site)
    deps.record("a:", recent)
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        attrib = el.attrib
        if not any(value and media in value for value in attrib.values()):
            continue
        items = []
        integrity = False
        for name, value in attrib.items():
            local = lxml.etree.QName(name).localname if "}" in name else name
            if value.startswith(media) and ATTRIBUTE.fullmatch(local):
                path = value[len(media) :]
                if not recent and path.startswith(("fonts/", "js/", "css/")):
                    fingerprint = site.fingerprint(path)
                    if fingerprint is not None:
                        prefix = "data-" if local.startswith("data-") else ""
                        items.append((name, media + fingerprint["path"]))
                        items.append((f"{prefix}integrity", fingerprint["integrity"]))
                        items.append(("crossorigin", "anonymous"))
                        integrity = True
                        continue
            items.append((name, rewrite_images(site, value)))
        if integrity:
            # Integrity attributes come right after the URL
            attrib.clear()
            for name, value in items:
                attrib[name] = value
        else:
            for name, value in items:
                if attrib[name] != value:
                    attrib[name] = value


def rewrite_images(site: Site, value: str) -> str:
    media = re.escape(site.mode.media_url)
    return re.sub(
        rf"(?:(?<=^)|(?<=,)){media}(images/[^ ,]+)(?=$| |,)",
        lambda mo: site.mode.media_url + site.hashed(mo.group(1)),
        value,
    )

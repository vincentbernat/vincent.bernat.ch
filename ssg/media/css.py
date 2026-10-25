"""Stylesheets, processed with PostCSS."""

from __future__ import annotations

import functools
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

from .. import config, deps
from ..tools import run

if TYPE_CHECKING:
    from ..model.site import Site

SCRIPT = Path(__file__).parent / "css.js"
SHARED = [
    config.CONTENT / "media" / "css" / "root.css",
    config.CONTENT / "media" / "css" / "common.css",
]
BASELINE_FONT = config.CONTENT / "media" / "fonts" / "literata.woff2"


@functools.cache
def baseline_offset(path: Path) -> float:
    """Baseline position as (ascent - descent) / (2 * upm) from OS/2 table."""
    xml = run("ttx", "-t", "OS/2", "-t", "head", "-o", "/dev/stdout", path)
    root = ET.fromstring(xml)
    upm = ttx_value(root, ".//head/unitsPerEm")
    ascent = ttx_value(root, ".//OS_2/sTypoAscender")
    descent = abs(ttx_value(root, ".//OS_2/sTypoDescender"))
    return (ascent - descent) / (2 * upm)


@functools.cache
def cap_offset(path: Path) -> float:
    """Space above capital letters minus space under the baseline, as
    (ascent - cap height - descent) / upm from OS/2 table."""
    xml = run("ttx", "-t", "OS/2", "-t", "head", "-o", "/dev/stdout", path)
    root = ET.fromstring(xml)
    upm = ttx_value(root, ".//head/unitsPerEm")
    ascent = ttx_value(root, ".//OS_2/sTypoAscender")
    descent = abs(ttx_value(root, ".//OS_2/sTypoDescender"))
    cap = ttx_value(root, ".//OS_2/sCapHeight")
    return (ascent - cap - descent) / upm


def ttx_value(root: ET.Element, path: str) -> int:
    element = root.find(path)
    value = element.get("value") if element is not None else None
    if value is None:
        raise ValueError(f"no {path} in ttx output")
    return int(value)


def process(site: Site, text: str) -> str:
    env = os.environ.copy()
    env["CSS_MINIFY"] = "true" if site.mode.production else "false"
    env["CSS_BASELINE_OFFSET"] = str(baseline_offset(BASELINE_FONT))
    env["CSS_CAP_OFFSET"] = str(cap_offset(BASELINE_FONT))
    return run("node", SCRIPT, "process", input=text, env=env)


@deps.cache
def value(expression: str) -> float:
    """Resolve a calc() expression against root.css variables to a rem
    value."""
    out = run(
        "node",
        SCRIPT,
        "calc",
        config.CONTENT / "media" / "css" / "root.css",
        expression,
    )
    mo = re.match(r"[\d.]+", out.strip())
    if mo is None:
        raise ValueError(f"cannot compute {expression}: {out}")
    return float(mo.group(0))


def page_width() -> tuple[int, int]:
    """Page width and breakpoint in pixels.

    The breakpoint matches the --lf-medium media query (--lf-vp-medium scaled
    by --lf-font-size). Below that viewport, the image fills 100vw. Above, it
    caps at page width.

    """
    px_per_em = 16
    page_width = value("calc(var(--lf-page-width) * var(--lf-font-size))")
    breakpoint = value("calc(var(--lf-vp-medium) * var(--lf-font-size))")
    return round(page_width * px_per_em), round(breakpoint * px_per_em)

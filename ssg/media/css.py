"""Stylesheets, processed with PostCSS."""

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .. import config, deps
from ..tools import run

SCRIPT = Path(__file__).parent / "css.js"
SHARED = [
    config.CONTENT / "media" / "css" / "root.css",
    config.CONTENT / "media" / "css" / "common.css",
]
BASELINE_FONT = config.CONTENT / "media" / "fonts" / "literata.woff2"


def baseline_offset(path):
    """Baseline position as (ascent - descent) / (2 * upm) from OS/2 table."""
    xml = run("ttx", "-t", "OS/2", "-t", "head", "-o", "/dev/stdout", path)
    root = ET.fromstring(xml)
    upm = int(root.find(".//head/unitsPerEm").get("value"))
    ascent = int(root.find(".//OS_2/sTypoAscender").get("value"))
    descent = abs(int(root.find(".//OS_2/sTypoDescender").get("value")))
    return (ascent - descent) / (2 * upm)


def process(site, text):
    env = os.environ.copy()
    env["CSS_MINIFY"] = "true" if site.mode.production else "false"
    env["CSS_BASELINE_OFFSET"] = str(baseline_offset(BASELINE_FONT))
    return run("node", SCRIPT, "process", input=text, env=env)


@deps.cache
def value(expression):
    """Resolve a calc() expression against root.css variables to a rem
    value."""
    out = run(
        "node",
        SCRIPT,
        "calc",
        config.CONTENT / "media" / "css" / "root.css",
        expression,
    )
    return float(re.match(r"[\d.]+", out.strip()).group(0))


def page_width():
    """Page width and breakpoint in pixels.

    The breakpoint matches the --lf-medium media query (--lf-vp-medium scaled
    by --lf-font-size). Below that viewport, the image fills 100vw. Above, it
    caps at page width.

    """
    px_per_em = 16
    page_width = value("calc(var(--lf-page-width) * var(--lf-font-size))")
    breakpoint = value("calc(var(--lf-vp-medium) * var(--lf-font-size))")
    return round(page_width * px_per_em), round(breakpoint * px_per_em)

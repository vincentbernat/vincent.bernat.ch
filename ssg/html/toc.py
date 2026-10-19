"""Table of contents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .dom import select

if TYPE_CHECKING:
    import lxml.etree

    from ..model.resource import Resource


def fix(resource: Resource, root: lxml.etree._Element) -> None:
    """Remove whitespaces inside UL and add a disclosure to expand the TOC."""
    for element in select(root, ".toc"):
        # The empty details element is only a switch: CSS uses its state to
        # display the TOC collapsed or expanded. It never hides anything.
        details = element.makeelement("details", {})
        summary = element.makeelement("summary", {"aria-label": resource.meta.l10n.toc})
        details.append(summary)
        details.tail = element.text
        element.text = None
        element.insert(0, details)
        for ul in element.iter("ul"):
            if len(ul) and ul[-1].tag == "li" and not (ul[-1].tail or "").strip():
                ul[-1].tail = None

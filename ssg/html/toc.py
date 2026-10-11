"""Table of contents."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..model.resource import Resource


def fix(resource: Resource, d: Any) -> None:
    """Remove whitespaces inside UL and add a disclosure to expand the TOC."""
    for element in d.items(".toc"):
        # The empty details element is only a switch: CSS uses its state to
        # display the TOC collapsed or expanded. It never hides anything.
        element.prepend(
            "<details>"
            f'<summary aria-label="{resource.meta.l10n.toc}"></summary>'
            "</details>"
        )
        html = element.outer_html()
        html = re.sub(r"</li>\s+</ul>", "</li></ul>", html)
        element.replace_with(html)

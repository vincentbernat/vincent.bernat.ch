"""Check that reference links have a definition.

Python-Markdown leaves `[text][label]` as-is when `label` has no definition, so
a typo goes unnoticed. Warn about it, and stop the build in production mode.
"""

import logging

from hyde.plugin import Plugin
from markdown.extensions import Extension

logger = logging.getLogger("hyde.markdown")

unknown = set()


class References(dict):
    """Link definitions, keeping track of the labels looked up in vain."""

    def __contains__(self, label):
        if super().__contains__(label):
            return True
        logger.warning("unknown reference: [%s]", label)
        unknown.add(label)
        return False


class ReferencesExtension(Extension):
    def extendMarkdown(self, md):
        md.registerExtension(self)
        md.references = References()


class ReferenceCheckPlugin(Plugin):
    """Stop the build when some references have no definition."""

    def site_complete(self):
        if unknown and self.site.config.mode == "production":
            raise RuntimeError(f"unknown references: {', '.join(sorted(unknown))}")


def makeExtension(**kwargs):
    return ReferencesExtension(**kwargs)

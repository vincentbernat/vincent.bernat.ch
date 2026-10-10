"""Check that reference links have a definition.

Python-Markdown leaves `[text][label]` as-is when `label` has no definition, so
a typo goes unnoticed.
"""

from markdown.extensions import Extension

from . import collect


class References(dict):
    """Link definitions, keeping track of the labels looked up in vain."""

    def __contains__(self, label):
        if super().__contains__(label):
            return True
        collect("references", label)
        return False


class ReferencesExtension(Extension):
    def extendMarkdown(self, md):
        md.registerExtension(self)
        md.references = References()


def makeExtension(**kwargs):
    return ReferencesExtension(**kwargs)

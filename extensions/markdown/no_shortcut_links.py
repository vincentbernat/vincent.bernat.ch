"""Disable shortcut reference links and images.

By default, `[label]` and `![label]` turn into a link or an image as soon as a
`[label]: url` definition exists. This is too easy to trigger by accident.
"""

from markdown.extensions import Extension


class NoShortcutLinksExtension(Extension):
    def extendMarkdown(self, md):
        md.registerExtension(self)
        md.inlinePatterns.deregister("short_reference")
        md.inlinePatterns.deregister("short_image_ref")


def makeExtension(**kwargs):
    return NoShortcutLinksExtension(**kwargs)

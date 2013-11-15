# -*- coding: utf-8 -*-
"""
CSS plugins
"""

from hyde.plugin import Plugin
import cssprefixer

class CSSPrefixerPlugin(Plugin):
    """Run CSS prefixer"""
    def text_resource_complete(self, resource, text):
        if not resource.source_file.kind in ("less", "css"):
            return
        return cssprefixer.process(text,
                                   debug=False,
                                   minify=True).replace("display:inline-block;",
                                                        "display:inline-block;zoom:1;*display:inline;")

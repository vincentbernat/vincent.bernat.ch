# -*- coding: utf-8 -*-
"""
Textlinks plugin
"""
import re

from hyde.plugin import Plugin


class TextlinksPlugin(Plugin):
    """
    The plugin class for syntax text replacement.
    """
    def __init__(self, site):
        super(TextlinksPlugin, self).__init__(site)

    def begin_text_resource(self, resource, text):
        """
        Replace content url pattern [[dm:XXXXX]] with something
        sensible. Currently, this is only Youtube stuff
        """
        if not resource.uses_template:
            return text
        link = re.compile('\[\[([a-z]+):([^\]]*)\]\]',
                          re.UNICODE | re.MULTILINE)

        def replace_content(match):
            what = match.group(1)
            id = match.group(2)

            if what == "youtube":
                return """
<div class="lf-video-container">
 <a class="lf-video" href="https://www.youtube.com/watch?v={id}">
  <div class="lf-video-play-button"></div>
  <img src="https://i.ytimg.com/vi/{id}/sddefault.jpg">
 </a>
</div>
""".format(id=id)

            return match.group(0)

        text = link.sub(replace_content, text)
        return text

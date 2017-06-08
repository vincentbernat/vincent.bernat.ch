# -*- coding: utf-8 -*-
"""
Media plugin
"""
import re

from hyde.plugin import Plugin


class MoreMediaPlugin(Plugin):
    """Replace some media links by the appropriate markup. Currently,
    this only supports the following YouTube markup:

        ![](youtube:XXXXXX)

    """
    def begin_text_resource(self, resource, text):
        if not resource.uses_template:
            return text
        youtube = re.compile(r'^!\[\]\(youtube:([\w-]+)\)$',
                             re.UNICODE | re.MULTILINE)

        def replace_content(match):
            return """
<div class="lf-video-outer"><div class="lf-video-inner">
 <a class="lf-video" href="https://www.youtube.com/watch?v={id}" title="YouTube video #{id}">
  YouTube video #{id}
  <div class="lf-video-play-button"></div>
 </a>
</div></div>
""".format(id=match.group(1))

        text = youtube.sub(replace_content, text)
        return text

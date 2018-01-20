# -*- coding: utf-8 -*-
"""
Media plugin
"""
import re

from hyde.plugin import Plugin


class MoreMediaPlugin(Plugin):
    """Replace some media links by the appropriate markup. Currently,
    this only supports the following YouTube markup:

        ![](video:XXXXXX)

    """
    def begin_text_resource(self, resource, text):
        if not resource.uses_template:
            return text
        video = re.compile(r'^!\[\]\(video:([\w-]+)\)$',
                           re.UNICODE | re.MULTILINE)

        def replace_content(match):
            return """
<div class="lf-video-outer"><div class="lf-video-inner">
 <video class="lf-video"
        src="https://luffy-video.sos-ch-dk-2.exo.io/{id}/playlist.m3u8"
        poster="https://luffy-video.sos-ch-dk-2.exo.io/{id}/poster.jpg"
        controls></video>
</div></div>
""".format(id=match.group(1))

        text = video.sub(replace_content, text)
        return text

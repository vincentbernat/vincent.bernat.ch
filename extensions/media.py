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
            # To check exact codec, see:
            #  https://stackoverflow.com/questions/16363167/html5-video-tag-codecs-attribute
            return """
<div class="lf-video-outer"><div class="lf-video-inner">
 <video class="lf-video"
        poster="https://luffy-video.sos-ch-dk-2.exo.io/{id}/poster.jpg"
        controls preload="none">
  <source src="https://luffy-video.sos-ch-dk-2.exo.io/{id}/index.m3u8" type="application/vnd.apple.mpegurl">
  <source src="https://luffy-video.sos-ch-dk-2.exo.io/{id}/progressive.mp4" type='video/mp4; codecs="avc1.4d401f, mp4a.40.2"'>
 </video>
</div></div>
""".format(id=match.group(1))

        text = video.sub(replace_content, text)
        return text

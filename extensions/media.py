# -*- coding: utf-8 -*-
"""
Media plugin
"""
import re

from hyde.plugin import Plugin


class MoreMediaPlugin(Plugin):
    """Replace some media links by the appropriate markup. Currently,
    this only supports the following markups:

        ![](video:XXXXXX)
        ![](audio:XXXXXX)

    """
    def begin_text_resource(self, resource, text):
        if not resource.uses_template:
            return text
        tags = re.compile(r'^!\[\]\(([a-z]+):([.\w-]+)\)$',
                          re.UNICODE | re.MULTILINE)

        def replace_content(match):
            if match.group(1) == "audio":
                audio = self.template.get_media_url_statement(
                    'audio/{id}'.format(id=match.group(2)))
                atype = ""
                if audio.endswith('.m4a'):
                    atype = """type='audio/mp4; codecs="mp4a.40.2"'"""
                return """
<audio controls preload="none" class="lf-audio">
 <source src="{audio}"{type}>
</audio>
    """.format(id=match.group(1), audio=audio, type=atype)
            elif match.group(1) == "video":
                # To check exact codec, see:
                #  https://stackoverflow.com/questions/16363167/html5-video-tag-codecs-attribute
                poster = self.template.get_media_url_statement(
                    'images/posters/{id}.jpg'.format(id=match.group(2)))
                return """
<div class="lf-video-outer"><div class="lf-video-inner">
 <video class="lf-video"
        poster="{poster}"
        controls preload="none">
  <source src="https://luffy-video.sos-ch-dk-2.exo.io/{id}/index.m3u8" type="application/vnd.apple.mpegurl">
  <source src="https://luffy-video.sos-ch-dk-2.exo.io/{id}/progressive.mp4" type='video/mp4; codecs="avc1.4d401f, mp4a.40.2"'>
 </video>
</div></div>
    """.format(id=match.group(2), poster=poster)

        text = tags.sub(replace_content, text)
        return text

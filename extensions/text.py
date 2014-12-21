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
        sensible. Currently, this is only DailyMotion stuff.
        """
        if not resource.uses_template:
            return text
        link = re.compile('\[\[([a-z]+):([^\]]*)\]\]', re.UNICODE|re.MULTILINE)
        def replace_content(match):
            what = match.group(1)
            id   = match.group(2)

            if what == "dailymotion":
                return """
<div class="lf-video-container"><div class="lf-video">
<iframe frameborder="0" width="480" height="270"
        src="//www.dailymotion.com/embed/video/%s"></iframe>
</div></div>
""" % (id,)
            if what == "youtube":
                return """
<div class="lf-video-container"><div class="lf-video">
<iframe frameborder="0" width="480" height="270" allowfullscreen
        src="//www.youtube-nocookie.com/embed/%s?rel=0"></iframe>
</div></div>
""" % (id,)

            return match.group(0)
        text = link.sub(replace_content, text)
        return text

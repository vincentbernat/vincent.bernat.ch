# -*- coding: utf-8 -*-
"""Plugin to select CDN depending on the path of the media file.

A `cdn` configuration block should be present. Depending on the path
of the file, a different media_url will be selected.

"""

from functools import wraps

from hyde.plugin import Plugin
from hyde.site import Site, _encode_path


def decorate_media_url(media_url):
    @wraps(media_url)
    def wrapper(site, path, safe=None):
        for block in site.config.cdn:
            if not path.startswith(block.path):
                continue
            return _encode_path(block.url,
                                path[len(block.path):],
                                safe)
        return media_url(site, path, safe)
    return wrapper


class CdnPlugin(Plugin):
    def __init__(self, site):
        super(CdnPlugin, self).__init__(site)

    def begin_site(self):
        """
        Initialize the plugin.

        We just decorate `Site.media_url` function.
        """
        Site.media_url = decorate_media_url(Site.media_url)

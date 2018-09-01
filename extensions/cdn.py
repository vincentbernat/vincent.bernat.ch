# -*- coding: utf-8 -*-
"""
Plugin to use a CDN for some static files
"""

import time

import os
from functools import wraps
from urllib import quote

from hyde.plugin import Plugin
from hyde.site import Site
from fswrap import FS, File, Folder

# Serve everything from CDN except content of files/ and videos/
NOCDN="https://media.luffy.cx/"
def decorate_media_url(media_url):
    @wraps(media_url)
    def wrapper(site, path, safe=None):
        if path.startswith("files/") or path.startswith("videos/"):
            # Don't use CDN for those big files
            base = NOCDN.encode('utf-8')
            path = path.strip().replace(os.sep, '/').encode('utf-8')
            path = quote(path, safe) if safe is not None else quote(path)
            return base.rstrip('/') + '/' + path.lstrip('/')
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

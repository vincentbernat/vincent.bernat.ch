# -*- coding: utf-8 -*-
"""
Contains classes to handle images related things

# Requires PIL/Pillow
"""

from hyde.plugin import Plugin
from hyde.plugin import CLTransformer
from hyde.ext.plugins.images import ImageSizerPlugin as _ImageSizerPlugin
from fswrap import File, Folder

import xml.etree.ElementTree as ET

from PIL import Image
import new
import os
from functools import partial

class Thumb(object):
    def __init__(self, path, **kwargs):
        self.path = path
        for arg in kwargs:
            setattr(self, arg, kwargs[arg])
    def __str__(self):
        return self.path       

def thumb(self, defaults={}, width=None, height=None):
    """
    Generate a thumbnail for the given image
    """
    if width is None and height is None:
        width, height = defaults['width'], defaults['height']
    im = Image.open(self.path)
    if im.mode != 'RGBA':
        im = im.convert('RGBA')
    # Convert to a thumbnail
    if width is None:
        # height is not None
        width = im.size[0]*height/im.size[1] + 1
    elif height is None:
        # width is not None
        height = im.size[1]*width/im.size[0] + 1
    im.thumbnail((width, height), Image.ANTIALIAS)
    # Prepare path
    path = os.path.join(os.path.dirname(self.get_relative_deploy_path()),
                        "%s%s" % (defaults['prefix'],
                                  self.name))
    target = File(Folder(self.site.config.deploy_root_path).child(path))
    target.parent.make()
    if self.name.endswith(".jpg"):
        im.save(target.path, "JPEG", optimize=True, quality=75)
    else:
        im.save(target.path, "PNG", optimize=True)
    return Thumb(path, width=im.size[0], height=im.size[1])

class ImageThumbnailsPlugin(Plugin):
    """
    Provide a function to get thumbnail for any image resource.

    Each image resource will get a `thumb()` function. This function
    can take the following keywords:
      - width (int)
      - height (int)
      - prefix (string): prefix to use for thumbnails

    This plugin can be configured with the exact same keywords to set
    site defaults. The `thumb()` function will return a path to the
    thumbnail. This path will have `width` and `height` as an
    attribute.

    Thumbnails are created in the same directory of their image.

    Currently, only supports PNG and JPG.
    """

    def __init__(self, site):
        super(ImageThumbnailsPlugin, self).__init__(site)

    def begin_site(self):
        """
        Find any image resource to add them the thumb() function.
        """
        # Grab default values from config
        config = self.site.config
        defaults = { "width": None,
                     "height": 40,
                     "prefix": 'thumb_',
                     }
        if hasattr(config, 'thumbnails'):
            defaults.update(config.thumbnails)
        # Make the thumbnailing function
        thumbfn = partial(thumb, defaults=defaults)
        thumbfn.__doc__ = "Create a thumbnail for this image"

        # Add it to any image resource
        for node in self.site.content.walk():
            for resource in node.resources:
                if resource.source_file.kind not in ["jpg", "png"]:
                    continue
                self.logger.debug("Adding thumbnail function to [%s]" % resource)
                resource.thumb = new.instancemethod(thumbfn, resource, resource.__class__)


class JPEGTranPlugin(CLTransformer):
    """
    The plugin class for JPEGTran
    """

    def __init__(self, site):
        super(JPEGTranPlugin, self).__init__(site)

    @property
    def plugin_name(self):
        """
        The name of the plugin.
        """
        return "jpegtran"

    def option_prefix(self, option):
        return "-"

    def binary_resource_complete(self, resource):
        """
        Run jpegtran to compress the jpg file.
        """

        if not resource.source_file.kind == 'jpg':
            return

        supported = [
            "optimize",
            "progressive",
            "restart",
            "arithmetic",
            "perfect",
            "copy",
        ]
        source = File(self.site.config.deploy_root_path.child(
                resource.relative_deploy_path))
        target = File.make_temp('')
        jpegtran = self.app
        args = [unicode(jpegtran)]
        args.extend(self.process_args(supported))
        args.extend(["-outfile", unicode(target), unicode(source)])
        self.call_app(args)
        target.copy_to(source)
        target.delete()


class ImageSizerPlugin(_ImageSizerPlugin):
    def _handle_img_size(self, image):
        if image.source_file.kind not in ['svg']:
            return super(ImageSizerPlugin, self)._handle_img_size(image)
        # We have a SVG, it should be quite easy, just take
        # width/height from svg root element.
        try:
            svg = ET.parse(image.path).getroot()
            return tuple(x and int(float(x)) or None
                         for x in (svg.attrib.get('width', None),
                                   svg.attrib.get('height', None)))
        except IOError:
            self.logger.warn("Unable to process image [%s]" % image)
            return (None, None)

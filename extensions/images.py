# -*- coding: utf-8 -*-
"""
Contains classes to handle images related things

# Requires PIL/Pillow
"""

import os
import re
import urllib
import xml.etree.ElementTree as ET
import lxml.html
import types
from functools import partial

from hyde.plugin import Plugin
from fswrap import File, Folder

from pyquery import PyQuery as pq
from PIL import Image
from pymediainfo import MediaInfo
import langcodes


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
    # Convert to a thumbnail
    if width is None:
        # height is not None
        width = im.size[0]*height//im.size[1] + 1
    elif height is None:
        # width is not None
        height = im.size[1]*width//im.size[0] + 1
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
        defaults = {
            "width": None,
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
                resource.thumb = types.MethodType(thumbfn, resource)


class ImageFixerPlugin(Plugin):
    """Fix images in various ways:

      - add width/height attributes
      - make them responsive
      - turn them into object if they are interactive
      - turn them into video if they are video
    """

    def __init__(self, site):
        super(ImageFixerPlugin, self).__init__(site)
        self.cache = {}

    def _topx(self, x):
        """Convert a size to pixels."""
        mo = re.match(r'(?P<size>\d+(?:\.\d*)?)(?P<unit>.*)', x)
        if not mo:
            raise ValueError("cannot convert {} to pixel".format(x))
        unit = mo.group("unit")
        size = float(mo.group("size"))
        if unit in {"", "px"}:
            return int(size)
        if unit == "pt":
            return int(size*4/3)
        raise ValueError("unknown unit {}".format(unit))

    def __size(self, image):
        """Get size for an image, and opacity."""
        if image.source_file.kind in {'png', 'jpg'}:
            img = Image.open(image.path)
            return img.size, "A" not in img.mode
        if image.source_file.kind in {'svg'}:
            svg = ET.parse(image.path).getroot()
            return tuple(x and self._topx(x) or None
                         for x in (svg.attrib.get('width', None),
                                   svg.attrib.get('height', None))), False
        if image.source_file.kind in {'m3u8'}:
            with open(image.path) as f:
                w, h = max([(int(w), int(h))
                            for w, h in re.findall('RESOLUTION=(\d+)x(\d+)(?:$|,)',
                                                   f.read())])
                return (w, h), True
        if image.source_file.kind in {'mp4', 'ogv'}:
            mi = MediaInfo.parse(image.path)
            track = [t for t in mi.tracks if t.track_type == 'Video'][0]
            return (track.width, track.height), True
        self.logger.warn(
            "[%s] has an img tag not linking to an image" % resource)
        return (None, None), True

    def _size(self, resource, src, width, height):
        """Determine size of an image (with cache)."""
        if src not in self.cache:
            if src.startswith(self.site.config.media_url):
                path = src[len(self.site.config.media_url):].lstrip("/")
                path = self.site.config.media_root_path.child(path)
                image = self.site.content.resource_from_relative_deploy_path(
                    path)
            elif src.startswith(self.site.media_url('videos/')):
                path = src[len(self.site.media_url('videos/')) -
                           len('videos/'):]
                path = self.site.config.media_root_path.child(path)
                image = self.site.content.resource_from_relative_deploy_path(
                    path)
            elif re.match(r'([a-z]+://|//).*', src):
                # Not a local link
                return None
            elif src.startswith("/"):
                # Absolute resource
                path = src.lstrip("/")
                image = self.site.content.resource_from_relative_deploy_path(
                    path)
            else:
                # Relative resource
                path = resource.node.source_folder.child(src)
                image = self.site.content.resource_from_path(path)
            if image is None:
                self.logger.warn(
                    "[%s] has an unknown image %s" % (resource, src))
                return None
            self.cache[src] = self.__size(image)
            self.logger.debug("Image [%s] is %s" % (src,
                                                    self.cache[src]))
        dim, opacity = self.cache[src]
        new_width, new_height = dim
        if new_width is None or new_height is None:
            return None
        if width is not None:
            return (width, int(width) * new_height // new_width)
        elif height is not None:
            return (int(height) * new_width // new_height, height)
        return (new_width, new_height)

    def _resize(self, source, destination, factor):
        """Resize provided image from source to destination with the provided
        factor. Check for latest modification time.
        """
        if not source.startswith(self.site.config.media_url):
            raise ValueError('[%s] cannot be resized' % source)
        source = source[len(self.site.config.media_url):].lstrip("/")
        source = self.site.config.media_root_path.child(source)
        source = self.site.content.resource_from_relative_deploy_path(source)
        if os.path.exists(os.path.join(os.path.dirname(source.path),
                                       destination)):
            # Image already provided with the correct size.
            return
        destination = os.path.join(
            os.path.dirname(self.site.config.deploy_root_path.child(source.relative_deploy_path)),
            destination)
        source = source.path
        if os.path.exists(destination) and os.stat(source).st_mtime < os.stat(destination).st_mtime:
            # Destination is more recent, assume size is correct
            return
        im = Image.open(source)
        im = im.resize((int(im.width*factor), int(im.height*factor)),
                       Image.ANTIALIAS)
        File(destination).parent.make()
        if source.endswith(".jpg"):
            im.save(destination, "JPEG", optimize=True, quality=95)
        else:
            im.save(destination, "PNG", optimize=True)

    def text_resource_complete(self, resource, text):

        """
        When the resource is generated, search for img tag and fix them.
        """
        if resource.source_file.name == 'atom.xml':
            root = ET.fromstring(text.encode('utf-8'))
            ET.register_namespace('', 'http://www.w3.org/2005/Atom')
            for c in root.findall('atom:entry/atom:content',
                                  {'atom': 'http://www.w3.org/2005/Atom'}):
                d = self._process(resource,
                                  u'<div>{}</div>'.format(c.text),
                                  ratio=False)
                c.text = d.html()
            return u'<?xml version="1.0" encoding="UTF-8"?>\n{}'.format(
                ET.tostring(root, encoding='unicode'))
        if not resource.source_file.kind == 'html':
            return

        d = self._process(resource, text)
        return u'<!DOCTYPE html>\n' + d.outer_html()

    def _process(self, resource, text, ratio=True):
        d = pq(text, parser='html')
        for img in d.items('img'):
            width = img.attr.width
            height = img.attr.height
            src = img.attr.src
            src = urllib.parse.unquote(src)
            if src is None:
                self.logger.warn(
                    "[%s] has an img tag without src attribute" % resource)
                continue
            if width is None or height is None:
                wh = self._size(resource, src, width, height)
                if wh is not None:
                    width, height = wh
                else:
                    width, height = None, None
            if width is not None:
                width, height = int(width), int(height)

            # Adapt width/height if this is a scaled image (something@2x.jpg)
            mo = re.match(r'.*@(\d+)x\.[^.]*$', src)
            if mo and width is not None:
                factor = int(mo.group(1))
                width //= factor
                height //= factor
                srcset = ['{} {}x'.format(src, factor)]
                for f in reversed(range(1, factor)):
                    tname = src.replace('@{}x.'.format(factor),
                                        '@{}x.'.format(f))
                    self._resize(src, os.path.basename(tname), float(f)/factor)
                    srcset.append('{} {}x'.format(tname, f))
                srcset = srcset[:-1]
                img.attr.src = tname
                img.attr.srcset = ','.join(srcset)

            # Put new width/height
            if width is not None:
                img.attr.width = '{}'.format(width)
                img.attr.height = '{}'.format(height)

            # If image is a SVG in /obj/, turns into an object
            if "/obj/" in src and src.endswith(".svg"):
                img[0].tag = 'object'
                img.attr("type", "image/svg+xml")
                img.attr("data", src)
                del img.attr.src
                img.text('&#128444; {}'.format(img.attr.alt or ""))

            # On-demand videos (should be in /videos)
            elif src.endswith('.m3u8'):
                id = os.path.splitext(os.path.basename(src))[0]
                img[0].tag = 'video'
                img[0].set("controls", None)
                img.attr("preload", "none")
                img.attr("crossorigin", "anonymous")
                img.attr("poster", self.site.media_url(
                    'images/posters/{}.jpg'.format(id)))
                del img.attr.src
                del img.attr.alt
                # Add sources
                m3u8 = pq('<source>')
                m3u8.attr.src = self.site.media_url(
                    'videos/{}.m3u8'.format(id))
                m3u8.attr.type = 'application/vnd.apple.mpegurl'
                img.append(m3u8)
                progressive = pq('<source>')
                progressive.attr.src = self.site.media_url(
                    'videos/{}/progressive.mp4'.format(id))
                progressive.attr.type = 'video/mp4; codecs="avc1.4d401f, mp4a.40.2"'
                img.append(progressive)
                # Add subtitle tracks if any
                vtts = [v
                        for v in self.site.content.node_from_relative_path(
                                "media/videos").walk_resources()
                        if v.name.endswith('.vtt')
                        and v.name.startswith('{}.'.format(id))]
                for vtt in vtts:
                    code = vtt.name[len(id)+1:-4]
                    track = pq('<track>')
                    track.attr.src = self.site.media_url(vtt.relative_path[6:])
                    track.attr.kind = 'subtitles'
                    track.attr.srclang = code
                    if resource.meta.language == code:
                        track[0].set("default", None)
                    if '-' not in code:
                        track.attr.label = langcodes.get(code).autonym()
                    else:
                        details = langcodes.get(code).describe(code)
                        lang = details['language']
                        del details['language']
                        track.attr.label = u"{} ({})".format(
                            lang, u", ".join(details.values()))
                    img.append(track)

            # If image is a video not in /videos turn into a simple
            # video tag like an animated GIF.
            elif src.endswith(".mp4") or src.endswith(".ogv"):
                img[0].tag = 'video'
                for attr in {'muted', 'loop', 'autoplay', 'playsinline', 'controls'}:
                    img[0].set(attr, None)
                del img.attr.alt

            # Lazy load if we have a large enough image
            if img[0].tag == "img" and width and width*height > 20000:
                img.attr.loading = "lazy"

            # If image is contained in a paragraph, enclose into a
            # responsive structure.
            parent = None
            parents = [p.tag for p in img.parents()]
            if parents[-1] == 'p':
                parent = img.parent()
            elif parents[-2:] == ['p', 'a']:
                parent = img.parent().parent()
            if parent:
                img.addClass('lf-media')
                inner = pq('<span />')
                outer = pq('<div />')
                inner.addClass('lf-media-inner')
                outer.addClass('lf-media-outer')
                if width is not None and ratio:
                    inner.css.padding_bottom = '{:.3f}%'.format(
                        float(height)*100./width)
                    outer.css.width = '{}px'.format(width)
                outer.append(inner)

                # Check opacity
                if src in self.cache:
                    _, opaque = self.cache[src]
                    if opaque:
                        img.addClass('lf-opaque')

                # If we have a title, also enclose in a figure
                figure = pq('<figure />')
                if img.attr.title:
                    figcaption = pq('<figcaption />')
                    figcaption.html(img.attr.title)
                    del img.attr.title
                    figure.append(outer)
                    figure.append(figcaption)
                else:
                    figure.append(outer)

                # Put image in inner tag
                if img.parent()[0].tag == 'a':
                    inner.append(img.parent())
                else:
                    inner.append(img)
                # Replace parent with our enclosure
                parent.replace_with(lxml.html.tostring(figure[0],
                                                       encoding='unicode'))

        return d

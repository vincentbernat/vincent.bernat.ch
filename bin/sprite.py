#!/usr/bin/python

# Create sprites from images given as an argument, to use them as
# CSS. Also provides CSS file.

IMGDIR="../images/l"
SPRITE="sprite.png"
CSS="../../css/luffy.sprite.less"
CLASS="lf-sprite"
SPACER=2

import sys
import os
import Image

css = """/* -*- css -*- */
/* Generated with %(args)s */

.%(class_)s {
    background: url('%(imgdir)s/%(sprite)s') no-repeat left top;
    display: inline-block;
}
""" % { "args":   " ".join(sys.argv),
        "class_": CLASS,
        "imgdir": IMGDIR,
        "sprite": SPRITE,
        }

# Get the total height and max width
width = 0
height = 0
for image in sys.argv[1:]:
    im = Image.open(image)
    height += im.size[1]
    if im.size[0] > width:
        width = im.size[0]
height += (len(sys.argv[1:]) - 1) * SPACER
sprite = Image.new('RGBA', (width, height))
height = 0
for image in sys.argv[1:]:
    im = Image.open(image)
    sprite.paste(im, (0, height))
    css += """
.%(class_)s-%(name)s {
    background-position: 0px %(offset)spx;
    width: %(width)spx;
    height: %(height)spx;
}
""" % { "class_": CLASS,
        "name":   os.path.basename(image).split(".")[0],
        "offset": -height,
        "width":  im.size[0],
        "height": im.size[1] }
    height += im.size[1] + SPACER
sprite.save(SPRITE, "PNG", optimize=True)
file(CSS, "w").write(css)

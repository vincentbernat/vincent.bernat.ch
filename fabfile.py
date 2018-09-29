# -*- coding: utf-8 -*-
from fabric.api import *
from fabric.contrib.console import confirm, prompt

import os
import shutil
import time
import json
import glob
import hashlib
import yaml
import csv
import re
import operator

env.shell = "/bin/sh -c"
env.command_prefixes = ['export PATH=$HOME/.virtualenvs/hyde/bin:$PATH']

conf = "site-production.yaml"
media = yaml.load(file(conf))['media_url']
hosts = ["web01.luffy.cx", "web02.luffy.cx", "web03.luffy.cx"]

def _hyde(args):
    return local('hyde -x %s' % args)

@task
def regen():
    """Regenerate dev content"""
    local('rm -rf deploy')
    gen()

@task
def gen():
    """Generate dev content"""
    _hyde('gen')

@task
def serve():
    """Serve dev content"""
    _hyde('serve -a 0.0.0.0')

@task
def sprite():
    """Regenerate sprites"""
    local(" ".join(["./node_modules/svg-sprite/bin/svg-sprite.js",
                    "--shape-spacing-padding=2px",
                    "--css",                         # CSS mode
                    "--css-bust=false",              # No cache busting
                    "--css-dest=content/media/css",  # Destination
                    "--css-prefix=.lf-sprite-",
                    "--css-dimensions=",             # Inline dimensions
                    "--css-mixin=sprite",
                    "--css-render-less",             # LESS mode
                    "--css-render-less-dest=luffy.sprite.less",
                    "--css-render-less-template=content/media/css/sprite.tmpl",
                    "--css-sprite=../images/l/sprite.svg",
                    "content/media/images/l/sprite/*.svg"]))
    # Convert to PNG
    with lcd("content/media/images/l"):
        local("inkscape --without-gui --export-png=sprite.png --export-area-page sprite.svg")
    # Add alternative to SVG
    local(r"sed -i '2s/\(.*\)\.svg\(.*\);/\1\.png\2;\n\1.svg\2, linear-gradient(transparent,transparent);/' content/media/css/luffy.sprite.less")

# For the following task, please check that the appropriate
# fonts are installed on the system. The rendering engine of both
# wkhtmltopdf and cutycapt is QT and it doesn't support web fonts
# yet. There is also a bug when multiple fonts are used under the same
# name. Here are the two relevant bugs:
#  https://code.google.com/p/wkhtmltopdf/issues/detail?id=145
#  https://code.google.com/p/wkhtmltopdf/issues/detail?id=783

@task
def screenshots():
    """Generate screenshots"""
    now = time.asctime().replace(" ", "-")
    os.makedirs("screenshots/{now}".format(now=now))
    for url in ["en/",
                "en/blog",
                "en/projects.html",
                "en/blog/2011-ssl-perfect-forward-secrecy.html",
                "en/blog/2011-thinkpad-edge-11.html"]:
        for width in [320, 600, 1024, 1280]:
            for js in ['on', 'off']:
                local("cutycapt "
                      "--url=http://localhost:8080/{url} "
                      "--out=screenshots/{now}/{width}px-js{js}-{slug}.png "
                      "--delay=1000 "
                      "--javascript={js} "
                      "--max-wait=5000 "
                      "--min-width={width}".format(width=width,
                                                   now=now,
                                                   url=url,
                                                   js=js,
                                                   slug=url.replace("/", "-").replace(".", "-")))

# Encoding of videos needs to be done with video2hls.
"""
while read video arguments; do
  video2hls --hls-playlist-prefix https://media.luffy.cx/videos/${video%.*}/ \
    --poster-grayscale --poster-quality 22 \
    $=arguments $video
done <<EOF
2012-multicast-vxlan.ogv         --video-bitrate-factor 0.3
2012-network-lab-kvm.ogv         --video-bitrate-factor 0.3
2013-exabgp-highavailability.ogv --video-bitrate-factor 0.3
2014-dashkiosk.ogv               --video-bitrate-factor 0.7
2014-eudyptula-boot-1.mp4        --video-bitrate-factor 0.5
2014-eudyptula-boot-2.mp4        --video-bitrate-factor 0.5
2015-hotfix-qemu-venom.mp4       --video-bitrate-factor 0.5
2017-netops-org-mode-1.mp4       --video-bitrate-factor 0.5
2017-netops-org-mode-2.mp4       --video-bitrate-factor 0.5
2017-netops-org-mode-3.mp4       --video-bitrate-factor 0.5
2018-adlib-opl2lpt-1-indy3.mp4   --video-bitrate-factor 0.5 \
                                 --audio-bitrate 128 --audio-only
2018-adlib-opl2lpt-2-indy4.mp4   --video-bitrate-factor 0.5 \
                                 --audio-bitrate 128 --audio-only
2018-adlib-opl2lpt-3-monkey2.mp4 --video-bitrate-factor 0.5 \
                                 --audio-bitrate 128 --audio-only
2018-self-hosted-videos.mp4      --mp4-overlay {resolution}p, progressive \
                                 --video-overlay {resolution}p, HLS
2018-opl2-audio-board-1.mp4      --video-bitrate-factor 0.3 \
                                 --audio-bitrate 128 --audio-only
2018-opl2-audio-board-2.mp4      --video-bitrate-factor 0.6 \
                                 --poster-seek 10% \
                                 --audio-bitrate 128 --audio-only
EOF
"""

# For 2018-adlib-opl2lpt.mp4, chapters have been included with
# "mp4chaps -i 2018-adlib-opl2lpt.mp4". It's not that useful (as we
# don't have support for them, but maybe at some point...)

# When possible, normalize videos to -2.0dB for peaks. Use the
# following command to get the peak volume:
#  ffmpeg -loglevel info -i indy3-dosbox-opl2lpt.mkv -af "volumedetect" -vn -sn -dn -f null /dev/null
#
# Then, in Blender, you can increase the volume (use
# http://www.redwirez.com/pcalc.jsp to convert dB to percents).

@task
def upload_videos(video=None):
    """Upload a transcoded video."""
    path = 'content/media/videos'
    for directory in os.listdir(path):
        if not os.path.isfile(os.path.join(path, directory, 'index.m3u8')):
            continue
        if video is not None and video != directory:
            continue
        # Upload
        for host in hosts:
            local("rsync -a {directory}/ {host}:/data/webserver/media.luffy.cx/videos/{short}/".format(
                host=host,
                short=directory,
                directory=os.path.join(path, directory)))
        # Copy poster and index.m3u8
        local("cp {directory}/poster.jpg content/media/images/posters/{short}.jpg".format(
            short=directory,
            directory=os.path.join(path, directory)))
        local("cp {directory}/index.m3u8 content/media/videos/{short}.m3u8".format(
            short=directory,
            directory=os.path.join(path, directory)))

@task
def linkcheck(remote='yes', verbose='no'):
    """Check links"""
    with settings(warn_only=True):
        result = local("linkchecker -f ./linkcheckerrc {} {}".format(
            verbose == 'yes' and '--verbose' or '',
            remote == 'yes' and
            'https://vincent.bernat.ch/' or
            'http://localhost:8080/'))
    if result.failed:
        fixlinks()

@task
def fixlinks():
    """Try to fix links"""
    fp = open("linkchecker-out.csv")
    reader = csv.DictReader(filter(lambda row: row[0]!='#', fp), delimiter=';')
    seen = {}
    for row in reader:
        if row['valid'] == 'True' and 'Redirected' not in row['infostring']:
            continue
        year = None
        archive = {}
        mo = re.search(r"/blog/(\d+)-", row['parentname'])
        if seen.get(row['urlname']):
            continue
        if mo:
            year = int(mo.group(1))
            archive = {'a': "https://archive.is/{}/{}".format(year, row['urlname']),
                       'w': "http{}://web.archive.org/web/{}/{}".format(
                           not row['urlname'].startswith('http:') and "s" or "",
                           year, row['urlname'])}
        while True:
            print """
URL:     {urlname}
Source:  {parentname}
Result:  {result}
Warning: {warningstring}
Info:    {infostring}""".format(**row)
            print """
(c) Continue
(b) Browse {urlname}
(p) Browse {parentname}
(r) Replace by your own URL
(q) Quit""".format(**row)
            valid = "cbprq"
            for a in archive:
                print "({}) Browse {}".format(a, archive[a])
                print "({}) Replace by {}".format(a.upper(), archive[a])
                valid += a
                valid += a.upper()
            if 'Redirected' in row['infostring']:
                mo = re.search(r'.*Redirected to `(.*?)\'\.', row['infostring'],
                               flags=re.DOTALL)
                if mo:
                    redirected = mo.group(1)
                    print "(R) Replace by {}".format(redirected)
                    valid += 'R'
            print
            ans = prompt("Command?", validate=r"[{}]".format(valid))
            if ans == "c":
                break
            elif ans == "q":
                return
            elif ans == "r":
                url = prompt("URL?")
                local("git grep -Fl '{}' | xargs -r sed -i 's+ {}+ {}+g'".format(
                    row['urlname'], row['urlname'], url))
                break
            elif ans == "b":
                local("x-www-browser {}".format(row['urlname']))
            elif ans == "p":
                local("x-www-browser {}".format(row['parentname']))
            elif ans == "R":
                local("git grep -Fl '{}' | xargs -r sed -i 's+ {}+ {}+g'".format(
                    row['urlname'], row['urlname'], redirected))
                break
            else:
                found = False
                for a in archive:
                    if ans == a:
                        local("x-www-browser {}".format(archive[a]))
                        break
                    elif ans == a.upper():
                        local("git grep -Fl '{}' | xargs -r sed -i 's+ {}+ {}+g'".format(
                            row['urlname'], row['urlname'], archive[a]))
                        found = True
                        break
                if found:
                    break
        seen[row['urlname']] = True

@task
def build():
    """Build production content"""
    local("[ $(git rev-parse --abbrev-ref HEAD) = master ]")
    local("rm -rf .final/*")
    _hyde('gen -c %s' % conf)
    with lcd(".final"):
        # Optimize SVG (consider using svgcleaner instead, svgo is a bit fragile)
        local("find media/images -type f -name '*.svg'"
              "| sed 's+/[^/]*$++' | sort | uniq"
              "| grep -Ev '^media/images/(l|obj)(/|$)'"
              "| xargs -n1 -P3 ../node_modules/svgo/bin/svgo --quiet --disable=mergePaths")
        local("find media/images -type f -name '*.svg'"
              "| grep -Ev '^media/images/(l|obj)(/|$)'"
              "| xargs -n1 -P3 sed -i 's/style=.marker:none. //g'")
        # Optimize JPG
        local("find media/images -type f -name '*.jpg' -print0"
              " | xargs -0 -n10 -P4 jpegoptim --max=84 --strip-all")
        local("find media/images -type f -name '*.jpg' -print0"
              " | xargs -0 -n1 -I'{}' -P4 jpegtran -optimize -progressive "
              "                                    -copy none -outfile '{}' '{}'")
        # Optimize PNG
        local("find media/images -type f -name '*.png' -print0"
              " | xargs -0 -n10 -P4 optipng -quiet")
        # Subset fonts. Nice tool to quickly look at the result:
        #  http://torinak.com/font/lsfont.html
        def subset(font, glyphs):
            options = " ".join(["--name-IDs+=0,4,6",
                                "--text-file=../glyphs-{}.txt".format(glyphs)])
            local("pyftsubset media/fonts/{}.woff  --flavor=woff --with-zopfli {}".format(font, options))
            local("pyftsubset media/fonts/{}.woff2 --flavor=woff2 {}".format(font, options))
            local("mv media/fonts/{}.subset.woff  media/fonts/{}.woff".format(font, font))
            local("mv media/fonts/{}.subset.woff2 media/fonts/{}.woff2".format(font, font))
        subset('iosevka-term', 'monospace')
        subset('merriweather', 'regular')
        subset('merriweather-italic', 'regular')
        # Compute hash on various files
        for p in ['media/images/l/sprite*.png',
                  'media/images/l/sprite*.svg',
                  'media/fonts/*',
                  'media/js/*.js',
                  'media/css/*.css']:
            sed_html = []
            sed_css = []
            files = local("echo %s" % p, capture=True).split(" ")
            for f in files:
                # Compute hash
                md5 = local("md5sum %s" % f, capture=True).split(" ")[0][:14]
                sha = local("openssl dgst -sha256 -binary %s | openssl enc -base64 -A" % f,
                            capture=True)
                print "[+] MD5/SHA hash for %s is %s and %s" % (f, md5, sha)
                # New name
                root, ext = os.path.splitext(f)
                newname = "%s.%s%s" % (root, md5, ext)
                local("cp %s %s" % (f, newname))
                # Remove deploy/media
                f = f[len('media/'):]
                newname = newname[len('media/'):]
                if ext in [".png", ".svg", ".woff", ".woff2"]:
                    # Fix CSS
                    sed_css.append('s+{})+{})+g'.format(f, newname))
                if ext not in [".png", ".svg", ".woff2"]:
                    # Fix HTML
                    sed_html.append(
                        (r"s,\([\"']\){}{}\1,\1{}{}\1 integrity=\1sha256-{}\1 crossorigin=\1anonymous\1,g"
                         "").format(media, f, media, newname, sha))
                if ext in [".woff2"]:
                    # Fix HTML
                    sed_html.append(
                        (r"s,\([\"']\){}{}\1,\1{}{}\1 integrity=\1sha256-{}\1 crossorigin=\1use-credentials\1,g"
                         "").format(media, f, media, newname, sha))
            if sed_css:
                local("find . -name '*.css' -type f -print0 | "
                      "xargs -r0 -n10 -P5 sed -i {}".format(
                          " ".join(("-e '{}'".format(x) for x in sed_css))))
            if sed_html:
                local("find . -name '*.html' -type f -print0 | "
                      "xargs -r0 -n10 -P5 sed -i {}".format(
                          " ".join(('-e "{}"'.format(x) for x in sed_html))))


        # Fix permissions
        local(r"find * -type f -print0 | xargs -r0 chmod a+r")
        local(r"find * -type d -print0 | xargs -r0 chmod a+rx")

        # For videos and files, use symlinks
        local("find media/files media/videos -type f -print0 "
              "  | xargs -0 -I'{}' ln -sf $PWD/../content/'{}' '{}'")

        local("git add *")
        local("git diff --stat HEAD || true")
        if confirm("More diff?", default=True):
            local("git diff --word-diff HEAD || true")
        if confirm("Keep?", default=True):
            local('git commit -a -m "Autocommit"')
        else:
            local("git reset --hard")
            local("git clean -d -f")
            abort("Build rollbacked")

@task
def push():
    """Push built site to production"""
    local("git push github")

    # media
    for host in hosts:
        local("rsync --exclude=.git --copy-unsafe-links -rc "
              ".final/media/ {}:/data/webserver/media.luffy.cx/".format(host))

    # HTML
    for host in hosts:
        local("rsync --exclude=.git --exclude=media --copy-unsafe-links -rc "
              ".final/ {}:/data/webserver/vincent.bernat.ch/".format(host))

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

@task
def transcode(video):
    """Transcode a video to HLS"""
    short = os.path.splitext(os.path.basename(video))[0]
    base = os.path.join(os.path.dirname(video), short)
    os.makedirs(base)
    with lcd(base):
        video = os.path.relpath(video, base)
        local("ffmpeg -loglevel error -ss 15 -i {video} "
              "-vframes 1 -vcodec png -an "
              "-vf select=\"eq(pict_type\\,I)\" "
              "-y poster.png".format(
                  video=video))
        local("convert poster.png -quality 10 poster.jpg")
        local("rm poster.png")
        # Get current format
        result = local("ffprobe -v quiet -print_format json -show_streams "
                       "{video}".format(video=video), capture=True)
        result = json.loads(result.stdout)
        result = [s for s in result['streams'] if s['codec_type'] == 'video'][0]
        oheight, owidth = result['height'], result['width']
        fps = operator.div(*[float(x)
                             for x in result['r_frame_rate'].split('/')])
        cmd = "ffmpeg -loglevel error -i {video} ".format(video=video)
        # See: https://docs.peer5.com/guides/production-ready-hls-vod/
        with open(os.path.join(base, "playlist.m3u8"), "w") as f:
            f.write("#EXTM3U\n")
            f.write("#EXT-X-VERSION:3\n")
            for q in [(1080, 4500, 128),
                      (720, 2500, 128),
                      (480, 1250, 96),
                      (360, 700, 96),
                      (240, 400, 64)]:
                height = q[0]
                width = (height*16/9)/2*2
                if height > oheight and width > owidth:
                    continue
                # We use FMP4. This requires iOS 10 or a browser
                # supporting media extensions. This is a more
                # efficient format than old TS format use with iOS <
                # 10.
                cmd += ("-f hls "
                        "-vf scale={width}:-2 "
                        "-profile:v baseline -level 3.0 "
                        "-c:a aac -ar 48000 -c:v h264 "
                        "-b:v {vrate}k -maxrate {mrate}k -bufsize {bufsize}k "
                        "-b:a {arate}k "
                        "-g {key} -keyint_min {key} "
                        "-hls_time 6 -hls_playlist_type vod -hls_list_size 0 "
                        "-hls_segment_type fmp4 "
                        "-hls_fmp4_init_filename {height}p-init.mp4 "
                        "-hls_segment_filename {height}p_%03d.mp4 "
                        "{height}p.m3u8 ").format(
                            video=video,
                            width=width, height=height,
                            key=int(fps*6.1),
                            vrate=q[1], bufsize=int(q[1]*1.5),
                            arate=q[2], mrate=q[1]+q[2])
                f.write("#EXT-X-STREAM-INF:"
                        "BANDWIDTH={vrate}000,"
                        "RESOLUTION={width}x{height},"
                        "NAME={height}p\n"
                        "{height}p.m3u8\n".format(height=height,
                                                  width=width,
                                                  vrate=q[1]))
            local(cmd)

@task
def upload(video):
    """Upload a transcoded video."""
    # Bucket needs to exist with CORS configuration:
    # <CORSConfiguration>
    #  <CORSRule>
    #    <AllowedOrigin>https://vincent.bernat.im</AllowedOrigin>
    #    <AllowedMethod>GET</AllowedMethod>
    #  </CORSRule>
    # </CORSConfiguration>
    short = os.path.splitext(os.path.basename(video))[0]
    base = os.path.join(os.path.dirname(video), short)
    with lcd(base):
        local("s3cmd --no-preserve -F -P --no-check-md5 "
              " --add-header=Cache-Control:'max-age=259200'" # 3 days
              " --mime-type=application/vnd.apple.mpegurl"
              " --encoding=UTF-8"
              " --exclude=* --include=*.m3u8"
              " --delete-removed"
              "   sync . s3://luffy-video/{short}/".format(short=short))
        local("s3cmd --no-preserve -F -P --no-check-md5 "
              " --add-header=Cache-Control:'max-age=259200'" # 3 days
              " --mime-type=image/jpeg"
              " --exclude=* --include=*.jpg"
              " --delete-removed"
              "   sync . s3://luffy-video/{short}/".format(short=short))
        local("s3cmd --no-preserve -F -P --no-check-md5 "
              " --add-header=Cache-Control:'max-age=259200'" # 3 days
              " --mime-type=video/mp4"
              " --exclude=* --include=*.mp4"
              " --delete-removed"
              "   sync . s3://luffy-video/{short}/".format(short=short))

@task
def linkcheck(remote='yes'):
    """Check links"""
    with settings(warn_only=True):
        result = local("linkchecker -f ./linkcheckerrc {}".format(
            remote == 'yes' and
            'https://vincent.bernat.im/' or
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
URL:    {urlname}
Source: {parentname}
Result: {result}""".format(**row)
            print """
(c) Continue
(b) Browse {urlname}
(p) Browse {parentname}
(r) Replace by your own URL
(q) Quit""".format(**row)
            valid = "cbqr"
            for a in archive:
                print "({}) Browse {}".format(a, archive[a])
                print "({}) Replace {} by {}".format(a.upper(), row['urlname'], archive[a])
                valid += a
                valid += a.upper()
            print
            ans = prompt("Command?", validate=r"[{}]".format(valid))
            if ans == "c":
                break
            elif ans == "q":
                return
            elif ans == "r":
                url = prompt("URL?")
                local("git grep -Fl '{}' | xargs sed -i 's+ {}+ {}+g'".format(
                    row['urlname'], row['urlname'], url))
                break
            elif ans == "b":
                local("x-www-browser {}".format(row['urlname']))
            else:
                found = False
                for a in archive:
                    if ans == a:
                        local("x-www-browser {}".format(archive[a]))
                        break
                    elif ans == a.upper():
                        local("git grep -Fl '{}' | xargs sed -i 's+ {}+ {}+g'".format(
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
        # Optimize SVG
        local("find media/images -type f -name '*.svg'"
              "| sed 's+/[^/]*$++' | sort | uniq"
              "| grep -v '^media/images/l$'"
              "| grep -v '^media/images/l/'"
              "| grep -v '^media/images/obj$'"
              "| grep -v '^media/images/obj/'"
              "| xargs -n1 ../node_modules/svgo/bin/svgo --quiet")
        # Subset fonts
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
            files = local("echo %s" % p, capture=True).split(" ")
            for f in files:
                if 'fonts/KaTeX' in f:
                    continue
                # Compute hash
                md5 = local("md5sum %s" % f, capture=True).split(" ")[0][:14]
                sha = local("openssl dgst -sha256 -binary %s | openssl enc -base64 -A" % f,
                            capture=True)
                print "[+] MD5/SHA hash for %s is %s and %s" % (f, md5, sha)
                # New name
                root, ext = os.path.splitext(f)
                newname = "%s.%s%s" % (root, md5, ext)
                # Symlink
                local("cp %s %s" % (f, newname))
                # Remove deploy/media
                f = f[len('media/'):]
                newname = newname[len('media/'):]
                if ext in [".png", ".svg", ".woff", ".woff2"]:
                    # Fix CSS
                    local("sed -i 's+%s)+%s)+g' media/css/*.css" % (f, newname))
                if ext not in [".png", ".svg"]:
                    # Fix HTML
                    local(r"find . -name '*.html' -type f -print0 | xargs -r0 sed -i "
                          '"'
                          r"s_\([\"']\)%s%s\1_\1%s%s\1 integrity=\1sha256-%s\1 crossorigin=\1anonymous\1_g"
                          '"' % (media, f, media, newname, sha))

        # Fix permissions
        local(r"find * -type f -print0 | xargs -r0 chmod a+r")
        local(r"find * -type d -print0 | xargs -r0 chmod a+rx")

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
    local("git push ace.luffy.cx")

    # media.luffy.cx
    local("rsync --exclude=.git -rlc .final/media/ ace.luffy.cx:/srv/www/luffy/media/")

    # HTML
    local("rsync --exclude=.git -rlc .final/ ace.luffy.cx:/srv/www/luffy/")

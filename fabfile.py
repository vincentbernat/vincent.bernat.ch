from fabric.api import *
from fabric.contrib.console import confirm

import os
import shutil
import time
import glob
import hashlib
import yaml

env.shell = "/bin/sh -c"
env.command_prefixes = [ 'export PATH=$HOME/.virtualenvs/hyde/bin:$PATH',
                         'export VIRTUAL_ENV=$HOME/.virtualenvs/hyde' ]

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
    with lcd("content/media/css"):
        local("glue --namespace=lf --simple --less ../images/l/sprite "
              "--css=. --img=../images/l")
        local("sed 's/ /display: inline-block; /' sprite.less > luffy.sprite.less")
        local("rm sprite.less")

# For the following task, please check that the appropriate
# fonts are installed on the system. The rendering engine of both
# wkhtmltopdf and cutycapt is QT and it doesn't support web fonts
# yet. There is also a bug when multiple fonts are used under the same
# name. Here are the two relevant bugs:
#  https://code.google.com/p/wkhtmltopdf/issues/detail?id=145
#  https://code.google.com/p/wkhtmltopdf/issues/detail?id=783
#
# Google Fonts can be downloaded from:
#   http://www.google.com/fonts#UsePlace:use/Collection:Source+Sans+Pro:700|Inconsolata|Merriweather:400,400italic

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
            local("cutycapt "
                  "--url=http://localhost:8080/{url} "
                  "--out=screenshots/{now}/{width}px-{slug}.png "
                  "--delay=1000 "
                  "--max-wait=5000 "
                  "--min-width={width}".format(width=width,
                                               now=now,
                                               url=url,
                                               slug=url.replace("/", "-").replace(".", "-")))

@task
def build():
    """Build production content"""
    local("git checkout master")
    local("rm -rf .final/*")
    _hyde('gen -c %s' % conf)
    with lcd(".final"):
        for p in [ 'media/images/l/sprite.png',
                   'media/js/*.js',
                   'media/css/*.css' ]:
            files = local("echo %s" % p, capture=True).split(" ")
            for f in files:
                # Compute hash
                md5 = local("md5sum %s" % f, capture=True).split(" ")[0][:8]
                print "[+] MD5 hash for %s is %s" % (f, md5)
                # New name
                root, ext = os.path.splitext(f)
                newname = "%s.%s%s" % (root, md5, ext)
                # Symlink
                local("cp %s %s" % (f, newname))
                # Remove deploy/media
                f = f[len('media/'):]
                newname = newname[len('media/'):]
                if ext == ".png":
                    # Fix CSS
                    local("sed -i 's@%s@%s@g' media/css/*.css" % (f, newname))
                else:
                    # Fix HTML
                    local(r"find . -name '*.html' -type f -print0 | xargs -r0 sed -i "
                          '"'
                          r"s@\([\"']\)%s%s\1@\1%s%s\1@g"
                          '"' % (media, f, media, newname))

        # Fix permissions
        local(r"find * -type f -print0 | xargs -r0 chmod a+r")
        local(r"find * -type d -print0 | xargs -r0 chmod a+rx")

        local("git add *")
        local("git diff --stat HEAD")
        if confirm("More diff?", default=True):
            local("git diff --word-diff HEAD")
        if confirm("Keep?", default=True):
            local('git commit -a -m "Autocommit"')
        else:
            local("git reset --hard")
            local("git clean -d -f")
            abort("Build rollbacked")

@task
def push():
    """Push built site to production"""
    push_main()
    push_s3()

@task
def push_main():
    """Push built site to ace"""
    local("git push github")
    local("git push ace.luffy.cx")

    # media.luffy.cx
    local("rsync --exclude=.git -a .final/media/ ace.luffy.cx:/srv/www/luffy/media/")

    # HTML
    local("rsync --exclude=.git -a .final/ ace.luffy.cx:/srv/www/luffy/")

def _s3cmd(args):
    local("s3cmd --exclude=.git/* --no-preserve --config=./s3cmd.cfg "
          "-F -P --no-check-md5 %s" % args)

@task
def push_s3():
    """Push built site to S3"""
    try:
        # This is a simplified version of the site. Notably, we
        # don't have a separate media site.
        local(r"find .final/* -type f -print0 | xargs -0 sed -i 's+\(src\|href\)=\"\(%s\|//media.luffy.cx/\)+\1=\"/media/+g'" % media)
        # Compress HTML, CSS and JS
        for t in "css js html".split():
            local(r"find .final/* -type f -name *.%s -exec gzip {} \; -exec mv {}.gz {} \;" % t)
        # In js/libs, never change, compress
        _s3cmd(" --add-header=Expires:'Thu, 31 Dec 2037 23:55:55 GMT'"
               " --add-header=Cache-Control:'max-age=315360000'"
               " --add-header=Content-Encoding:'gzip'"
               " --mime-type=application/x-javascript"
               " --encoding=UTF-8"
               "   sync .final/media/js/libs/ s3://vincent.bernat.im/media/js/libs/")
        # JS and CSS in media, 30 days, compress
        _s3cmd(" --add-header=Cache-Control:'max-age=2592000'" # 30 days
               " --add-header=Content-Encoding:'gzip'"
               " --mime-type=application/x-javascript"
               " --encoding=UTF-8"
               " --exclude=* --include=*.js"
               "   sync .final/media/ s3://vincent.bernat.im/media/")
        _s3cmd(" --add-header=Cache-Control:'max-age=2592000'" # 30 days
               " --add-header=Content-Encoding:'gzip'"
               " --mime-type=text/css"
               " --encoding=UTF-8"
               " --exclude=* --include=*.css"
               "   sync .final/media/ s3://vincent.bernat.im/media/")
        # Other files in media, 30 days, don't compress
        _s3cmd(" --add-header=Cache-Control:'max-age=2592000'" # 30 days
               "   sync .final/media/ s3://vincent.bernat.im/media/")
        _s3cmd(" --add-header=Cache-Control:'max-age=2592000'" # 30 days
               "   sync .final/media/favicon.ico s3://vincent.bernat.im/")
        # HTML files, 1h, compress
        _s3cmd(" --add-header=Cache-Control:'max-age=3600'" # 1h
               " --add-header=Content-Encoding:'gzip'"
               " --mime-type=text/html"
               " --encoding=UTF-8"
               " --exclude=* --include=*.html"
               "   sync .final/ s3://vincent.bernat.im/")
        # Remaining files, 1h, don't compress
        _s3cmd(" --add-header=Cache-Control:'max-age=3600'" # 1h
               " --exclude=media/* --exclude=nginx.conf"
               "   sync .final/ s3://vincent.bernat.im/")
    finally:
        with lcd(".final"):
            local("git reset --hard")

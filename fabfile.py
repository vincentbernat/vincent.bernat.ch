from fabric.api import *

import os
import shutil
import time
import glob
import hashlib
import yaml

env.shell = "/bin/sh -c"
env.command_prefixes = [ 'export PATH=$HOME/.virtualenvs/hyde/bin:$PATH',
                         'export VIRTUAL_ENV=$HOME/.virtualenvs/hyde' ]

def _hyde(args):
    return local('python ../hyde/h %s' % args)

def regen():
    """Regenerate dev content"""
    local('rm -rf deploy')
    gen()

def gen():
    """Generate dev content"""
    _hyde('gen')

def serve():
    """Serve dev content"""
    _hyde('serve -a 0.0.0.0')

def sprite():
    """Regenerate sprites"""
    with lcd("content/media/css"):
        local("glue --namespace=lf --simple --less ../images/l/sprite "
              "--css=. --img=../images/l")
        local("sed 's/ /display: inline-block; /' sprite.less > luffy.sprite.less")
        local("rm sprite.less")

def build():
    """Build production content"""
    local("git checkout master")
    local("rm -rf .final/*")
    conf = "site-production.yaml"
    media = yaml.load(file(conf))['media_url']
    _hyde('gen -c %s' % conf)
    with lcd(".final"):
        for p in [ 'media/js/*.js',
                   'media/css/*.css',
                   'media/images/l/sprite.png' ]:
            files = local("echo %s" % p, capture=True).split(" ")
            for f in files:
                # Compute hash
                md5 = local("md5sum %s" % f, capture=True).split(" ")[0][:8]
                print "[+] MD5 hash for %s is %s" % (f, md5)
                # New name
                root, ext = os.path.splitext(f)
                newname = "%s.%s%s" % (root, md5, ext)
                # Symlink
                local("ln -s %s %s" % (os.path.basename(f), newname))
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
        answer = prompt("More diff?", default="yes")
        if answer.lower().startswith("y"):
            local("git diff --word-diff HEAD")
        answer = prompt("Keep?", default="yes")
        if answer.lower().startswith("y"):
            local('git commit -a -m "Autocommit"')
        else:
            local("git reset --hard")
            local("git clean -d -f")

def push():
    """Push production content to ace"""
    local("git push github")
    local("git push ace.luffy.cx")


    # media.luffy.cx
    local("rsync --exclude=.git -a .final/media/ ace.luffy.cx:/srv/www/luffy/media/")

    # HTML
    local("rsync --exclude=.git -a .final/ ace.luffy.cx:/srv/www/luffy/")

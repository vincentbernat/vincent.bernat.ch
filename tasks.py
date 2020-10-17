# -*- coding: utf-8 -*-
from invoke import task

import os
import sys
import time
import yaml
import csv
import re
import datetime

os.environ["PATH"] = os.path.expanduser('~/.virtualenvs/hyde/bin') \
    + os.pathsep + os.environ["PATH"]

conf = "site-production.yaml"
media = yaml.safe_load(open(conf))['media_url']
hosts = ["web03.luffy.cx", "web04.luffy.cx"]


def confirm(question, default=False):
    if default:
        suffix = "Y/n"
    else:
        suffix = "y/N"
    while True:
        response = input("{0} [{1}] ".format(question, suffix))
        response = response.lower().strip()  # Normalize
        # Default
        if not response:
            return default
        if response in ["y", "yes"]:
            return True
        if response in ["n", "no"]:
            return False
        err = "I didn't understand you. Please specify '(y)es' or '(n)o'."
        print(err, file=sys.stderr)


@task
def gen(c):
    """Generate dev content"""
    c.run('hyde -x gen')


@task(post=[gen])
def regen(c):
    """Regenerate dev content"""
    c.run('rm -rf deploy')


@task
def serve(c):
    """Serve dev content"""
    c.run('hyde -x serve -a 0.0.0.0', pty=True)


@task
def sprite(c):
    """Regenerate sprites"""
    c.run(" ".join(["./node_modules/svg-sprite/bin/svg-sprite.js",
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


@task
def screenshots(c):
    """Generate screenshots"""
    now = time.asctime().replace(" ", "-")
    os.makedirs("screenshots/{now}".format(now=now))
    for url in ["en/",
                "en/blog",
                "en/projects.html",
                "en/blog/2011-ssl-perfect-forward-secrecy.html",
                "en/blog/2011-thinkpad-edge-11.html",
                "en/blog/2017-ipv6-route-lookup-linux.html"]:
        for width in [320, 600, 1024, 1280, 1900]:
            c.run("chromium "
                  "--headless "
                  "--hide-scrollbars "
                  "--screenshot "
                  "--disable-gpu "
                  "--window-size={width},2000 "
                  "http://localhost:8080/{url} "
                  "&& mv screenshot.png "
                  "   screenshots/{now}/{width}px-{slug}.png".format(
                      width=width,
                      now=now,
                      url=url,
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
2019-self-hosted-videos-subtitles.webm \
                                 --poster-seek 15s
EOF
"""

# For 2018-adlib-opl2lpt.mp4, chapters have been included with
# "mp4chaps -i 2018-adlib-opl2lpt.mp4". It's not that useful (as we
# don't have support for them, but maybe at some point...)

# When possible, normalize videos to -2.0dB for peaks. Use the
# following command to get the peak volume:
#  ffmpeg -loglevel info -i indy3-dosbox-opl2lpt.mkv -af "volumedetect" \
#         -vn -sn -dn -f null /dev/null
#
# Then, in Blender, you can increase the volume (use
# http://www.redwirez.com/pcalc.jsp to convert dB to percents).


@task
def upload_videos(c, video=None):
    """Upload a transcoded video."""
    path = 'content/media/videos'
    for directory in os.listdir(path):
        if not os.path.isfile(os.path.join(path, directory, 'index.m3u8')):
            continue
        if video is not None and video != directory:
            continue
        # Upload
        for host in hosts:
            c.run("rsync -a {directory}/ {host}:"
                  "/data/webserver/media.luffy.cx/videos/{short}/".format(
                      host=host,
                      short=directory,
                      directory=os.path.join(path, directory)))
        # Copy poster and index.m3u8
        c.run("cp {directory}/poster.jpg "
              "content/media/images/posters/{short}.jpg".format(
                  short=directory,
                  directory=os.path.join(path, directory)))
        c.run("cp {directory}/index.m3u8 "
              "content/media/videos/{short}.m3u8".format(
                  short=directory,
                  directory=os.path.join(path, directory)))


@task
def update_monospace_fonts(c):
    """Build latest Iosevka fonts with Nix"""
    c.run("""
nix-build -E '((import <nixpkgs>{}).iosevka.override {
  privateBuildPlan = {
    family = "Iosevka Custom";
    design = ["custom" "term" "ss05" "v-asterisk-low"];
    slants = {
      upright = "upright";
    };
    weights = {
      regular = {
        shape = 300;
        menu = 400;
        css = 400;
      };
    };
  };
  set = "custom";
}).overrideAttrs(oldAttrs: {
  postConfigure = "cat <<EOF > private.toml
[custom]
xheight = 560
cap = 775
EOF";
})'
""")
    c.run("cp result/share/fonts/iosevka-custom/*.ttf content/media/fonts/.")
    c.run("rm result")
    with c.cd("content/media/fonts"):
        c.run("woff iosevka-custom*.ttf")
        c.run("woff2_compress iosevka-custom*.ttf")
        c.run("rm iosevka-custom*.ttf")


@task
def update_text_fonts(c):
    """Download latest Merriweather fonts"""
    url = "https://github.com/SorkinType/Merriweather/raw/master/fonts/woff2"
    with c.cd('content/media/fonts'):
        for source, target in [("Merriweather-Light", "merriweather"),
                               ("Merriweather-LightItalic", "merriweather-italic")]:
            c.run("wget -O {}.woff2 "
                  "{}/{}.woff2".format(target, url, source))
            # Patch
            c.run('ttx -o - {}.woff2 '
                  '| xmlstarlet ed '
                  '     -u /ttFont/post/underlineThickness/@value -v 150 '
                  '> {}.ttx'.format(target, target))
            c.run('ttx -o {}.woff --flavor=woff {}.ttx'.format(target, target))
            c.run('ttx -o {}.woff2 --flavor=woff2 {}.ttx'.format(target, target))
            c.run('rm {}.ttx'.format(target))


@task
def linkcheck(c, remote=True, verbose=False):
    """Check links"""
    result = c.run("nix run nixpkgs.linkchecker -c linkchecker -f ./linkcheckerrc {} {}".format(
        verbose and '--verbose' or '',
        remote and
        'https://vincent.bernat.ch/' or
        'http://localhost:8080/'), warn=True)
    if result.failed:
        fixlinks(c)


@task
def fixlinks(c):
    """Try to fix links"""
    fp = open("linkchecker-out.csv")
    reader = csv.DictReader(filter(lambda row: row[0] != '#', fp),
                            delimiter=';')
    seen = {}
    for row in reader:
        if row['valid'] == 'True' and 'Redirected' not in row['infostring']:
            continue
        year = datetime.datetime.now().year
        archive = {}
        mo = re.search(r"/blog/(\d+)-", row['parentname'])
        if seen.get(row['urlname']):
            continue
        if mo:
            year = int(mo.group(1))
        archive = {'a': "https://archive.today/{}/{}".format(year,
                                                             row['urlname']),
                   'w': "http{}://web.archive.org/web/{}/{}".format(
                       not row['urlname'].startswith('http:') and "s" or "",
                       year, row['urlname'])}
        while True:
            print("""
URL:     {urlname}
Source:  {parentname}
Result:  {result}
Warning: {warningstring}
Info:    {infostring}""".format(**row))
            print("""
(c) Continue
(b) Browse {urlname}
(p) Browse {parentname}
(r) Replace by your own URL
(q) Quit""".format(**row))
            valid = "cbprq"
            for a in archive:
                print("({}) Browse {}".format(a, archive[a]))
                print("({}) Replace by {}".format(a.upper(), archive[a]))
                valid += a
                valid += a.upper()
            if 'Redirected' in row['infostring']:
                mo = re.search(r'.*Redirected to `(.*?)\'\.',
                               row['infostring'],
                               flags=re.DOTALL)
                if mo:
                    redirected = mo.group(1)
                    print("(R) Replace by {}".format(redirected))
                    valid += 'R'
            print()
            ans = input("Command? ")
            if ans not in valid:
                continue
            if ans == "c":
                break
            elif ans == "q":
                return
            elif ans == "r":
                url = input("URL? ")
                c.run("git grep -Fl '{}'"
                      "| xargs -r sed -i 's, {}, {},g'".format(
                          row['urlname'], row['urlname'], url))
                break
            elif ans == "b":
                c.run("xdg-open {}".format(row['urlname']))
            elif ans == "p":
                c.run("xdg-open {}".format(row['parentname']))
            elif ans == "R":
                c.run("git grep -Fl '{}'"
                      "| xargs -r sed -i 's, {}, {},g'".format(
                          row['urlname'], row['urlname'], redirected))
                break
            else:
                found = False
                for a in archive:
                    if ans == a:
                        c.run("xdg-open {}".format(archive[a]))
                        break
                    elif ans == a.upper():
                        c.run("git grep -Fl '{}'"
                              "| xargs -r sed -i 's, {}, {},g'".format(
                                  row['urlname'], row['urlname'], archive[a]))
                        found = True
                        break
                if found:
                    break
        seen[row['urlname']] = True


@task
def build(c):
    """Build production content"""
    with c.cd("content/en"):
        c.run("! git grep -Pw '((?i:"
              "obviously|basically|simply|clearly|everyone knows|turns out"
              "|explicitely|overriden|accross"
              ")|Thinkpad)' \\*.html")
        c.run("! git grep -E '\"[.](\s|$)' \\*.html")
    c.run("[ $(git rev-parse --abbrev-ref HEAD) = latest ]")
    c.run('git annex lock && [ -z "$(git status --porcelain)" ]')
    c.run("rm -rf .final/*")
    c.run("yarn install --frozen-lockfile")
    c.run('hyde -x gen -c %s' % conf)
    with c.cd(".final"):
        # Fix HTML (<source> is an empty tag)
        c.run(r"find . -name '*.html' -print0"
              r"| xargs -0 sed -i 's+\(<source[^>]*>\)</source>+\1+g'")
        c.run(r"find . -name '*.html' -print0"
              r"| xargs -0 sed -i 's+\(<track[^>]*>\)</track>+\1+g'")
        # Optimize SVG (consider using svgcleaner instead, svgo is a
        # bit fragile)
        c.run("find media/images -type f -name '*.svg'"
              "| sed 's+/[^/]*$++' | sort | uniq"
              "| grep -Ev '^media/images/(l|obj)(/|$)'"
              "| sort "
              "| xargs -n1 -P3 ../node_modules/svgo/bin/svgo "
              "        --quiet --disable=mergePaths")
        c.run("find media/images -type f -name '*.svg'"
              "| grep -Ev '^media/images/(l|obj)(/|$)'"
              "| xargs -n1 -P3 sed -i 's/style=.marker:none. //g'")
        # Optimize JPG
        jpegoptim = c.run("nix-build --no-out-link "
                          "  -E 'with (import <nixpkgs>{}); "
                          "        jpegoptim.override { libjpeg = mozjpeg; }'").stdout.strip()
        c.run("find media/images -type f -name '*.jpg' -print0"
              "  | sort -z "
              f" | xargs -0 -n10 -P4 {jpegoptim}/bin/jpegoptim --max=84 --all-progressive --strip-all")
        # Optimize PNG
        c.run("find media/images -type f -name '*.png' -print0"
              " | sort -z "
              " | xargs -0 -n10 -P4 pngquant --skip-if-larger --strip "
              "                              --quiet --ext .png --force "
              "|| true")

        # Subset fonts. Nice tool to quickly look at the result:
        #  http://torinak.com/font/lsfont.html
        def subset(font, glyphs, options=[]):
            options = " ".join(["--layout-features=liga,kern",
                                "--text-file=../glyphs-{}.txt".format(glyphs),
                                "--no-hinting --desubroutinize",
                                *options])
            c.run("pyftsubset media/fonts/{}.woff "
                  "--flavor=woff --with-zopfli {}".format(font, options))
            c.run("pyftsubset media/fonts/{}.woff2 "
                  "--flavor=woff2 {}".format(font, options))
            c.run("mv media/fonts/{}.subset.woff "
                  "media/fonts/{}.woff".format(font, font))
            c.run("mv media/fonts/{}.subset.woff2 "
                  "media/fonts/{}.woff2".format(font, font))
        subset('iosevka-custom-regular', 'monospace')
        subset('merriweather', 'regular', ["--layout-features+=ss01"])
        subset('merriweather-italic', 'regular', ["--layout-features+=ss01"])
        # Compute hash on various files
        for p in ['media/images/l/sprite*.svg',
                  'media/fonts/*',
                  'media/js/*.js',
                  'media/css/*.css']:
            sed_html = []
            sed_css = []
            files = c.run("echo %s" % p, hide=True).stdout.strip().split(" ")
            for f in files:
                # Compute hash
                md5 = c.run("md5sum %s" % f,
                            hide="out").stdout.split(" ")[0][:14]
                sha = c.run("openssl dgst -sha256 -binary %s"
                            "| openssl enc -base64 -A" % f,
                            hide="out").stdout.strip()
                # New name
                root, ext = os.path.splitext(f)
                newname = "%s.%s%s" % (root, md5, ext)
                c.run("cp %s %s" % (f, newname))
                # Remove deploy/media
                f = f[len('media/'):]
                newname = newname[len('media/'):]
                if ext in [".png", ".svg", ".woff", ".woff2"]:
                    # Fix CSS
                    sed_css.append('s+{})+{})+g'.format(f, newname))
                if ext not in [".png", ".svg"]:
                    # Fix HTML
                    sed_html.append(
                        (r"s,"
                         r"\(data-\|\)\([a-z]*=\)\([\"']\){}{}\3,"
                         r"\1\2\3{}{}\3 \1integrity=\3sha256-{}\3 "
                         r"crossorigin=\3anonymous\3,"
                         r"g").format(media, f, media, newname, sha))
            if sed_css:
                c.run("find . -name '*.css' -type f -print0 | "
                      "xargs -r0 -n10 -P5 sed -i {}".format(
                          " ".join(("-e '{}'".format(x) for x in sed_css))))
            if sed_html:
                c.run("find . -name '*.html' -type f -print0 | "
                      "xargs -r0 -n10 -P5 sed -i {}".format(
                          " ".join(('-e "{}"'.format(x) for x in sed_html))))

        # Fix permissions
        c.run(r"find * -type f -print0 | xargs -r0 chmod a+r")
        c.run(r"find * -type d -print0 | xargs -r0 chmod a+rx")

        c.run("git add *")
        c.run("git diff --stat HEAD || true", pty=True)
        if confirm("More diff?", default=True):
            c.run("git diff --word-diff HEAD || true", pty=True)
        if confirm("Keep?", default=True):
            c.run('git commit -a -m "Autocommit"')
        else:
            c.run("git reset --hard")
            c.run("git clean -d -f")
            raise RuntimeError("Build rollbacked")


@task
def push(c, clean=False):
    """Push built site to production"""
    c.run("git push github")

    with c.cd(".final"):
        # Restore timestamps (this relies on us not truncating
        # history too often)
        c.run('''
for f in $(git ls-tree -r -t --full-name --name-only HEAD); do
    touch -d $(git log --pretty=format:%cI -1 HEAD -- "$f") -h "$f";
done''')

    # media
    for host in hosts:
        c.run("rsync --exclude=.git --copy-unsafe-links -rt "
              ".final/media/ {}:/data/webserver/media.luffy.cx/".format(host))

    # HTML
    for host in hosts:
        c.run("rsync --exclude=.git --exclude=media "
              "--delete-delay --copy-unsafe-links -rt "
              ".final/ {}:/data/webserver/vincent.bernat.ch/".format(host))

    if clean:
        for host in hosts:
            c.run("rsync --exclude=.git --copy-unsafe-links -rt "
                  "--delete-delay --exclude=videos/\\*/ "
                  ".final/media/ "
                  "{}:/data/webserver/media.luffy.cx/".format(host))


@task
def analytics(c):
    """Get some stats"""
    c.run("for h in {};"
          "do ssh $h zcat -f /var/log/nginx/vincent.bernat.ch.log\\*"
          "   | grep -v atom.xml;"
          "done"
          " | LANG=en_US.utf8 goaccess "
          "       --ignore-crawlers "
          "       --http-protocol=no "
          "       --no-term-resolver "
          "       --no-ip-validation "
          "       --output=goaccess.html "
          "       --log-format=COMBINED "
          "       --ignore-panel=KEYPHRASES "
          "       --ignore-panel=REQUESTS_STATIC "
          "       --ignore-panel=GEO_LOCATION "
          "       --sort-panel=REQUESTS,BY_VISITORS,DESC "
          "       --sort-panel=NOT_FOUND,BY_VISITORS,DESC "
          "       --sort-panel=HOSTS,BY_VISITORS,DESC "
          "       --sort-panel=OS,BY_VISITORS,DESC "
          "       --sort-panel=BROWSERS,BY_VISITORS,DESC "
          "       --sort-panel=REFERRERS,BY_VISITORS,DESC "
          "       --sort-panel=REFERRING_SITES,BY_VISITORS,DESC "
          "       --sort-panel=STATUS_CODES,BY_VISITORS,DESC "
          "".format(" ".join(hosts)))
    c.run("xdg-open goaccess.html")

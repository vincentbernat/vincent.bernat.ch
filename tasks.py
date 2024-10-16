# -*- coding: utf-8 -*-
from invoke import task

import os
import sys
import time
import yaml
import csv
import re
import datetime
import contextlib
import urllib
import urllib.request
import binascii
import base64
import xml.etree.ElementTree as ET

conf = "site-production.yaml"
media = yaml.safe_load(open(conf))["media_url"]
hosts = [
    "web02.luffy.cx",
    "web03.luffy.cx",
    "web04.luffy.cx",
    "web05.luffy.cx",
    "web06.luffy.cx",
]


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


@contextlib.contextmanager
def step(what):
    green = "\033[32;1m"
    blue = "\033[34;1m"
    yellow = "\033[33;1m"
    reset = "\033[0m"
    now = time.time()
    print(f"{blue}▶ {yellow}{what}{reset}...", file=sys.stderr)
    yield
    elapsed = int(time.time() - now)
    print(f"{blue}▶ {green}{what}{reset} ({elapsed}s)", file=sys.stderr)


@task
def gen(c):
    """Generate dev content"""
    c.run("hyde -x gen")


@task(post=[gen])
def regen(c):
    """Regenerate dev content"""
    c.run("rm -rf deploy")


@task
def serve(c):
    """Serve dev content"""
    c.run("hyde -x serve -a 0.0.0.0", pty=True, hide=False)


@task
def prune(c, before="1 year ago"):
    """Prune old commits."""
    with c.cd(".final"):
        out = c.run(
            f"git log --before='{before}' --pretty=format:%H | head -1"
        ).stdout.strip()
        assert out != ""
        c.run(f"echo {out} > .git/shallow")
        c.run("git gc --prune=now")


@task
def archive(c, lang="en", pause=2):
    """Archive on the Wayback Machine."""
    ns = {"urlset": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    sitemap = f".final/{lang}/sitemap.xml"
    locs = ET.parse(sitemap).getroot().findall(".//urlset:loc", ns)
    locs.reverse()
    for loc in locs:
        for url in loc.itertext():
            print(f"Archive {url}...")
            request_url = f"https://web.archive.org/save/{url}"
            try:
                with urllib.request.urlopen(request_url):
                    print(f"200 OK: {url}")
            except urllib.error.HTTPError as err:
                print(f"{err.code} {err.reason}: {url}")
            finally:
                time.sleep(pause)


@task
def screenshots(c):
    """Generate screenshots"""
    now = time.asctime().replace(" ", "-")
    os.makedirs("screenshots/{now}".format(now=now))
    for url in [
        "en/",
        "en/blog",
        "en/projects.html",
        "en/blog/2011-ssl-perfect-forward-secrecy.html",
        "en/blog/2011-thinkpad-edge-11.html",
        "en/blog/2017-ipv6-route-lookup-linux.html",
        "en/blog/2020-old-pc-cards.html",
        "en/blog/2019-self-hosted-videos-subtitles.html",
    ]:
        for width in [320, 600, 1024, 1280, 1900]:
            c.run(
                "chromium "
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
                    slug=url.replace("/", "-").replace(".", "-"),
                )
            )


# Encoding of videos needs to be done with video2hls.
"""
while read video arguments; do
  video2hls --hls-playlist-prefix https://media.bernat.ch/videos/${video%.*}/ \
    --poster-grayscale --poster-quality 30 \
    $=arguments -- $video
done <<EOF
2012-multicast-vxlan.ogv         --video-bitrate-factor 0.3
2012-network-lab-kvm.ogv         --video-bitrate-factor 0.3
2013-exabgp-highavailability.ogv --video-bitrate-factor 0.3
2014-dashkiosk.ogv               --video-bitrate-factor 0.7
2014-eudyptula-boot-1.mp4        --video-bitrate-factor 0.5
2014-eudyptula-boot-2.mp4        --video-bitrate-factor 0.5
2015-hotfix-qemu-venom.mp4       --video-bitrate-factor 0.5
2015-dotscale-docker-machine-swarm.mkv \
                                 --video-bitrate-factor 0.3
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
2021-network-cmdb.mkv            --video-bitrate-factor 0.5 \
                                 --poster-seek 20%
2021-frnog34-jerikan.mp4         --video-bitrate-factor 0.5
2022-clickhouse-meetup-akvorado.mkv \
                                 --video-widths 1280 428 \
                                 --video-bitrates 500 100
2022-frnog36-akvorado.mp4        --video-bitrate-factor 0.5
EOF
"""

# For 2018-adlib-opl2lpt.mp4, chapters have been included with
# "mp4chaps -i 2018-adlib-opl2lpt.mp4". It's not that useful (as we
# don't have support for them, but maybe at some point...)

# When possible, normalize videos to -2.0dB for peaks. Use the
# following command to get the peak volume:
#  ffmpeg -loglevel info -i 2021-network-cmdb.mkv -af "volumedetect" -vn -sn -dn -f null /dev/null
#
# Then, to normalize (where 6.4dB is the desired offset compared to max)
#  ffmpeg -i 2021-network-cmdb.mkv -filter:a "volume=6.4dB" -c:v copy normalized.mkv


@task
def upload_videos(c, video=None):
    """Upload a transcoded video."""
    path = "content/media/videos"
    for directory in os.listdir(path):
        if not os.path.isfile(os.path.join(path, directory, "index.m3u8")):
            continue
        if video is not None and video != directory:
            continue
        # Upload
        for host in hosts:
            c.run(
                "rsync --delete --info=progress2 -a {directory}/ {host}:"
                "/data/webserver/media.bernat.ch/videos/{short}/".format(
                    host=host, short=directory, directory=os.path.join(path, directory)
                ),
                hide=False,
            )
        # Copy poster and index.m3u8
        c.run(
            "cp {directory}/poster.jpg "
            "content/media/images/posters/{short}.jpg".format(
                short=directory, directory=os.path.join(path, directory)
            )
        )
        c.run(
            "cp {directory}/index.m3u8 "
            "content/media/videos/{short}.m3u8".format(
                short=directory, directory=os.path.join(path, directory)
            )
        )


@task
def update_fonts(c):
    """Build fonts with Nix"""
    # We can compare the metrics using http://webfont-test.com/
    with step("building Iosevka"):
        c.run("nix build .#build.iosevka")
        c.run(
            "install -m 0644 result/Iosevka*.woff2 content/media/fonts/iosevka-custom-regular.woff2"
        )
        c.run("rm result")
    with step("building Merriweather"):
        c.run("nix build .#build.merriweather")
        c.run("install -m 0644 result/*.woff2 content/media/fonts/")
        c.run("rm result")


@task
def linkcheck(c, remote=True, verbose=False):
    """Check links"""
    result = c.run(
        "nix run .#linkchecker -- -f ./linkcheckerrc {} {}".format(
            verbose and "--verbose" or "",
            remote and "https://vincent.bernat.ch/" or "http://localhost:8080/",
        ),
        warn=True,
        hide=False,
    )
    if result.failed:
        fixlinks(c)


@task
def fixlinks(c):
    """Try to fix links"""
    fp = open("linkchecker-out.csv")
    reader = csv.DictReader(filter(lambda row: row[0] != "#", fp), delimiter=";")
    seen = {}
    for row in reader:
        if row["valid"] == "True" and "Redirected" not in row["infostring"]:
            continue
        year = datetime.datetime.now().year
        archive = {}
        mo = re.search(r"/blog/(\d+)-", row["parentname"])
        if seen.get(row["urlname"]):
            continue
        if mo:
            year = int(mo.group(1))
        archive = {
            "a": "https://archive.today/{}/{}".format(year, row["urlname"]),
            "w": "https://web.archive.org/web/{}/{}".format(
                year,
                row["urlname"],
            ),
        }
        while True:
            print(
                """
URL:     {urlname}
Source:  {parentname}
Result:  {result}
Warning: {warningstring}
Info:    {infostring}""".format(
                    **row
                )
            )
            print(
                """
(c) Continue
(b) Browse {urlname}
(p) Browse {parentname}
(r) Replace by your own URL
(q) Quit""".format(
                    **row
                )
            )
            valid = "cbprq"
            for a in archive:
                print("({}) Browse {}".format(a, archive[a]))
                print("({}) Replace by {}".format(a.upper(), archive[a]))
                valid += a
                valid += a.upper()
            if "Redirected" in row["infostring"]:
                mo = re.search(
                    r".*Redirected to `(.*?)\'\.", row["infostring"], flags=re.DOTALL
                )
                if mo:
                    redirected = mo.group(1)
                    print("(R) Replace by {}".format(redirected))
                    valid += "R"
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
                c.run(
                    "git grep -Fl '{}'"
                    r"| xargs -r sed -i 's|\([( ]\){}|\1{}|g'".format(
                        row["urlname"], row["urlname"], url
                    )
                )
                break
            elif ans == "b":
                c.run("xdg-open '{}'".format(row["urlname"]))
            elif ans == "p":
                c.run("xdg-open '{}'".format(row["parentname"]))
            elif ans == "R":
                c.run(
                    "git grep -Fl '{}'"
                    r"| xargs -r sed -i 's|\([( ]\){}|\1{}|g'".format(
                        row["urlname"], row["urlname"], redirected
                    )
                )
                break
            else:
                found = False
                for a in archive:
                    if ans == a:
                        c.run("xdg-open '{}'".format(archive[a]))
                        break
                    elif ans == a.upper():
                        c.run(
                            "git grep -Fl '{}'"
                            "| xargs -r sed -i 's| {}| {}|g'".format(
                                row["urlname"], row["urlname"], archive[a]
                            )
                        )
                        found = True
                        break
                if found:
                    break
        seen[row["urlname"]] = True


@task
def build(c):
    """Build production content"""
    with c.cd("content/en"):
        c.run(
            "! git grep -Pw '((?i:"
            "obviously|basically|simply|clearly|everyone knows|turns out"
            "|explicitely|overriden|accross|totally|equipments"
            ")|Thinkpad)' \\*.html",
            hide="out",
        )
        c.run(r"! git grep -E '\"[.](\s|$)' \*.html")
    c.run('git annex lock && [ -z "$(git status --porcelain)" ]')
    c.run("rm -rf .final/*")
    with step("run Hyde"):
        c.run("hyde -x gen -c %s" % conf)
    with c.cd(".final"):
        # Fix HTML (<source> is an empty tag)
        with step("fix HTML"):
            c.run(
                r"find . -name '*.html' -print0"
                r"| xargs -0 sed -i 's+\(<source[^>]*>\)</source>+\1+g'"
            )
            c.run(
                r"find . -name '*.html' -print0"
                r"| xargs -0 sed -i 's+\(<track[^>]*>\)</track>+\1+g'"
            )

        with step("subset fonts"):
            c.run(
                """
cd ..
env NIX_PATH=fonts=$PWD/.final/media/fonts:monospace=$PWD/glyphs-monospace.txt:regular=$PWD/glyphs-regular.txt \
  nix build --impure .#build.subsetFonts
cd -
cp -r --no-preserve=mode ../result/* media/fonts/.
rm ../result
"""
            )

        # Compute hash on various files
        with step("cache busting and SRI"):
            # First fonts and images, then JS and CSS
            for directories in [("fonts", "images"), ("js", "css")]:
                directories = " ".join(f"media/{d}" for d in directories)
                md5 = c.run(
                    f"find {directories} -type f -print0 | xargs -0 md5sum", hide=True
                ).stdout.strip()
                md5 = {
                    line.split("  ")[1][6:]: line.split("  ")[0][:14]
                    for line in md5.split("\n")
                }
                sha256 = c.run(
                    f"find {directories} -type f -print0 | xargs -0 sha256sum",
                    hide=True,
                ).stdout.strip()
                sha256 = {
                    line.split("  ")[1][6:]: line.split("  ")[0]
                    for line in sha256.split("\n")
                }
                sha256 = {
                    k: base64.b64encode(binascii.unhexlify(sha256[k])).decode("ascii")
                    for k in sha256
                }
                sed_html = []
                sed_css = []
                for f in md5:
                    if f == "images/favicon.png":
                        continue
                    root, ext = os.path.splitext(f)
                    newname = "%s.%s%s" % (root, md5[f], ext)
                    c.run("mv media/%s media/%s" % (f, newname))
                    # Fix CSS
                    sed_css.append(f"s+{f})+{newname})+g")
                    # Fix HTML
                    if not f.startswith("images/"):
                        sed_html.append(
                            r"s,"
                            rf"\(data-\|\)\([a-z]*=\)\([\"']\){media}{f}\3,"
                            rf"\1\2\3{media}{newname}\3 \1integrity=\3sha256-{sha256[f]}\3 "
                            r"crossorigin=\3anonymous\3,"
                            r"g"
                        )
                    else:
                        sed_html.append(
                            r"s,"
                            rf"\([a-z-]*=\)\([\"']\){media}{f}\(\2\| \),"
                            rf"\1\2{media}{newname}\3,"
                            r"g"
                        )
                while sed_css:
                    c.run(
                        "find . -name '*.css' -type f -print0 | "
                        "xargs -r0 -n10 -P5 sed -i {}".format(
                            " ".join(("-e '{}'".format(x) for x in sed_css[:20]))
                        )
                    )
                    sed_css = sed_css[20:]
                while sed_html:
                    c.run(
                        "(find . -name '*.html' -type f -print0 ; find . -name 'atom.xml' -print0) | "
                        "xargs -r0 -n10 -P5 sed -i {}".format(
                            " ".join(('-e "{}"'.format(x) for x in sed_html[:20]))
                        )
                    )
                    sed_html = sed_html[20:]

        # Image optimization
        with step("optimize images"):
            c.run(
                "cd .. ; NIX_PATH=target=$PWD/.final/media/images nix build --impure .#build.optimizeImages"
            )
            c.run("cp -r --no-preserve=mode ../result/* media/images/. && rm ../result")

        # We want to prefer JPGs if their sizes are not too large.
        # The idea is that:
        #  - JPG decoding is fast
        #  - JPG has progressive decoding
        #
        # We prefer smaller WebPs over AVIFs as all browsers
        # supporting AVIF also support WebP.
        with step("remove WebP/AVIF files not small enough"):
            c.run(
                "for f in media/images/**/*.{webp,avif}; do"
                "  orig=$(stat --format %s ${f%.*});"
                "  new=$(stat --format %s $f);"
                "  (( $orig*0.90 > $new )) || rm $f;"
                "done",
                shell="/bin/zsh",
            )
            c.run(
                "for f in media/images/**/*.avif; do"
                "  [[ -f ${f%.*}.webp ]] || continue;"
                "  orig=$(stat --format %s ${f%.*}.webp);"
                "  new=$(stat --format %s $f);"
                "  (( $orig > $new )) || rm $f;"
                "done",
                shell="/bin/zsh",
            )
            c.run(
                r"""
printf "     %10s %10s %10s\n" Original WebP AVIF
printf " PNG %10s %10s %10s\n" \
   $(find media/images -name '*.png' | wc -l) \
   $(find media/images -name '*.png.webp' | wc -l) \
   $(find media/images -name '*.png.avif' | wc -l)
printf " JPG %10s %10s %10s\n" \
   $(find media/images -name '*.jpg' | wc -l) \
   $(find media/images -name '*.jpg.webp' | wc -l) \
   $(find media/images -name '*.jpg.avif' | wc -l)
            """,
                hide="err",
            )

        # Fix permissions
        c.run(r"find * -type f -print0 | xargs -r0 chmod a+r")
        c.run(r"find * -type d -print0 | xargs -r0 chmod a+rx")

        # Delete unwanted files
        c.run("find . -type f -name '.*' -delete")
        c.run(
            r"find media/videos -type l -regextype egrep  \! -regex '.*\.(m3u8|vtt|txt)$' -delete"
        )

        c.run("git add *")
        c.run("git diff --stat HEAD || true", pty=True, hide=False)
        if confirm("More diff?", default=True):
            c.run(
                "env GIT_PAGER=less git diff --word-diff HEAD || true",
                pty=True,
                hide=False,
            )
        if confirm("Keep?", default=True):
            c.run('git commit -a -m "Autocommit"', hide=False)
        else:
            c.run("git reset --hard")
            c.run("git clean -d -f")
            raise RuntimeError("Build rollbacked")


@task
def image_quality(c, extension="jpg", target_extension=""):
    """Compare image compression"""
    c.run(
        rf"""
count=0
total=0
for f in $(cd content/media ; find images -name '*.{extension}'); do
  [ -f .final/media/$f{target_extension} ] || continue
  ssim=$(magick compare -metric SSIM \
           content/media/$f \
           .final/media/$f{target_extension} \
           /dev/null 2>&1)
  count=$((count+1))
  total=$((total+ssim))
done
echo "SSIM {extension} to {extension}{target_extension}: $((total/count)) (out of $count)"
""",
        shell="/bin/zsh",
    )


@task
def push(c, clean=False):
    """Push built site to production"""
    with step("push to GitHub"):
        c.run("git push github")

    with c.cd(".final"):
        # Restore timestamps (this relies on us not truncating
        # history too often)
        with step("restore timestamps"):
            c.run(
                """
for f in $(git ls-tree -r -t --full-name --name-only HEAD); do
    touch -d $(git log --pretty=format:%cI -1 HEAD -- "$f") -h "$f";
done"""
            )

    # media
    for host in hosts:
        with step(f"push media to {host}"):
            c.run(
                "rsync --exclude=.git --copy-unsafe-links -rt "
                ".final/media/ {}:/data/webserver/media.bernat.ch/".format(host)
            )

    # HTML
    for host in hosts:
        with step(f"push HTML to {host}"):
            c.run(
                "rsync --exclude=.git --exclude=media "
                "--delete-delay --copy-unsafe-links -rt "
                ".final/ {}:/data/webserver/vincent.bernat.ch/".format(host)
            )
            c.run("ssh {} sudo systemctl reload nginx".format(host))

    if clean:
        for host in hosts:
            with step(f"clean files on {host}"):
                c.run(
                    "rsync --exclude=.git --copy-unsafe-links -rt "
                    "--delete-delay "
                    "--include='**/' "
                    "--include='*.avif' --include='*.webp' "
                    "--exclude='*' "
                    ".final/media/images "
                    "{}:/data/webserver/media.bernat.ch/".format(host)
                )
                c.run(
                    "rsync --exclude=.git --copy-unsafe-links -rt "
                    "--delete-delay --exclude=videos/\\*/ "
                    ".final/media/ "
                    "{}:/data/webserver/media.bernat.ch/".format(host)
                )


@task
def analytics(c, pattern=""):
    """Get some stats"""
    c.run(
        "for h in {};"
        "do ssh -C $h zcat -f /var/log/nginx/vincent.bernat.ch.log\\*"
        f"   | grep -aFv atom.xml | grep -F '{pattern}';"
        "done"
        " | LANG=en_US.utf8 nix run .#goaccess -- "
        "       --ignore-crawlers "
        "       --unknowns-as-crawlers "
        "       --http-protocol=no "
        "       --no-term-resolver "
        "       --no-ip-validation "
        "       --no-query-string "
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
        "".format(" ".join(hosts)),
        hide=False,
    )
    c.run("xdg-open goaccess.html")

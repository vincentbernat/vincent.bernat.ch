from invoke import task, Exit

import os
import sys
import time
import yaml
import csv
import re
import json
import shlex
import pty
import select
import subprocess
import tempfile
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
mpl_cache = os.path.expanduser("~/.cache/matplotlib")
os.makedirs(mpl_cache, exist_ok=True)
bwrap = (
    "bwrap "
    "--ro-bind / / --dev /dev --proc /proc "
    "--tmpfs /run --tmpfs /tmp --tmpfs /var/tmp --tmpfs $HOME "
    "--bind $PWD $PWD "
    f"--bind {mpl_cache} {mpl_cache} "
    "--unshare-all --die-with-parent "
)


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


def human(size):
    if size < 1024:
        return f"{size} B"
    for unit in ("KiB", "MiB"):
        size /= 1024
        if size < 1024:
            return f"{size:.1f} {unit}"
    return f"{size / 1024:.1f} GiB"


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
def build_dev(c, clean=False):
    """Generate dev content"""
    if clean:
        c.run("rm -rf deploy")
    c.run("[ ! -d deploy ] || find deploy -perm 444 -delete")
    c.run(f"{bwrap} -- hyde -x gen")


@task
def build_pagefind(c, site="deploy"):
    """Run pagefind indexation"""
    c.run(
        f"{bwrap} -- node_modules/pagefind/lib/runner/bin.cjs "
        f"--site {site} "
        "--exclude-selectors=.headerlink "
        "--output-subdir=media/js/pagefind"
    )
    with c.cd(f"{site}/media/js/pagefind"):
        c.run(
            "rm pagefind-component* pagefind-modular* pagefind-ui* pagefind-worker* pagefind-highlight.js"
        )
    with c.cd(f"{site}/media"):
        c.run("mkdir -p pagefind")
        c.run("mv js/pagefind/pagefind.js js")
        c.run("mv js/pagefind/* pagefind")
        c.run("rmdir js/pagefind")


@task
def serve(c):
    """Serve dev content behind nginx"""

    def spawn(command):
        """Run a command in the background, attached to a pty to keep colors."""
        master, slave = pty.openpty()
        process = subprocess.Popen(
            f"exec {command}",
            shell=True,
            stdin=subprocess.DEVNULL,
            stdout=slave,
            stderr=slave,
            start_new_session=True,
        )
        os.close(slave)
        process.output = master
        return process

    def mux(processes, until):
        """Display the outputs of the given processes until one of them exits."""
        colors = ["\033[36m", "\033[35m"]
        reset = "\033[0m"
        outputs = {
            process.output: (f"{colors[idx % len(colors)]}{name:5}{reset} │ ", b"")
            for idx, (name, process) in enumerate(processes.items())
        }
        while until.poll() is None and outputs:
            ready, _, _ = select.select(list(outputs), [], [], 0.2)
            for fd in ready:
                prefix, pending = outputs[fd]
                try:
                    data = os.read(fd, 65536)
                except OSError:
                    data = b""
                if not data:
                    del outputs[fd]
                    continue
                lines = (pending + data.replace(b"\r", b"")).split(b"\n")
                outputs[fd] = (prefix, lines.pop())
                for line in lines:
                    print(f"{prefix}{line.decode('utf-8', 'replace')}", flush=True)

    # Ports are also set in layout/nginx.j2
    hyde_port = 8081
    processes = {}
    try:
        with tempfile.TemporaryDirectory(prefix="nginx-") as run:
            processes["hyde"] = spawn(
                f"{bwrap} --share-net -- hyde -x serve -s -a 127.0.0.1 -p {hyde_port}"
            )
            curl = subprocess.Popen(
                shlex.split(
                    "curl -sS --retry 10 --retry-connrefused --retry-all-errors "
                    f"-o {run}/nginx.conf http://127.0.0.1:{hyde_port}/nginx.conf"
                )
            )
            mux(processes, until=curl)
            if curl.wait() != 0:
                raise Exit("unable to get the nginx configuration")
            processes["nginx"] = spawn(f"nginx -p {run} -c {run}/nginx.conf")
            mux(processes, until=processes["nginx"])
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes.values():
            process.terminate()


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


# Additional video2hls arguments for each video.
video_arguments = {
    "2012-multicast-vxlan.ogv": "--video-bitrate-factor 0.3 --no-audio",
    "2012-network-lab-kvm.ogv": "--video-bitrate-factor 0.3 --no-audio",
    "2013-exabgp-highavailability.ogv": "--video-bitrate-factor 0.3",
    "2014-dashkiosk.ogv": "--video-bitrate-factor 0.7",
    "2014-eudyptula-boot-1.mp4": "--video-bitrate-factor 0.5",
    "2014-eudyptula-boot-2.mp4": "--video-bitrate-factor 0.5",
    "2015-hotfix-qemu-venom.mp4": "--video-bitrate-factor 0.5",
    "2015-dotscale-docker-machine-swarm.mkv": "--video-bitrate-factor 0.3",
    "2017-netops-org-mode-1.mp4": "--video-bitrate-factor 0.5",
    "2017-netops-org-mode-2.mp4": "--video-bitrate-factor 0.5",
    "2017-netops-org-mode-3.mp4": "--video-bitrate-factor 0.5",
    "2018-adlib-opl2lpt-1-indy3.mp4": (
        "--video-bitrate-factor 0.5 --audio-bitrate 128 --audio-only"
    ),
    "2018-adlib-opl2lpt-2-indy4.mp4": (
        "--video-bitrate-factor 0.5 --audio-bitrate 128 --audio-only"
    ),
    "2018-adlib-opl2lpt-3-monkey2.mp4": (
        "--video-bitrate-factor 0.5 --audio-bitrate 128 --audio-only"
    ),
    "2018-self-hosted-videos.mp4": (
        "--mp4-overlay '{resolution}p, progressive' "
        "--video-overlay '{resolution}p, HLS'"
    ),
    "2018-opl2-audio-board-1.mp4": (
        "--video-bitrate-factor 0.3 --audio-bitrate 128 --audio-only"
    ),
    "2018-opl2-audio-board-2.mp4": (
        "--video-bitrate-factor 0.6 --poster-seek 10% --audio-bitrate 128 --audio-only"
    ),
    "2019-self-hosted-videos-subtitles.webm": "--poster-seek 15s",
    "2021-network-cmdb.mkv": "--video-bitrate-factor 0.5 --poster-seek 20%",
    "2021-frnog34-jerikan.mp4": "--video-bitrate-factor 0.5",
    "2022-clickhouse-meetup-akvorado.mkv": (
        "--video-widths 1280 428 --video-bitrates 500 100"
    ),
    "2022-frnog36-akvorado.mp4": "--video-bitrate-factor 0.5",
    "2026-spanning-tree.mp4": "--video-bitrate-factor 0.25",
}


@task
def video_encode(c, video=None, skipifexists=False):
    """Encode a video to HLS with video2hls."""
    if video is None:
        for video in video_arguments:
            with step(f"encoding {video}"):
                video_encode(c, video, True)
        return
    if video not in video_arguments:
        raise Exit(f"unknown video {video}, add it to video_arguments")
    short = os.path.splitext(video)[0]
    if skipifexists and os.path.isdir(f"content/media/videos/{short}"):
        return
    with c.cd("content/media/videos"):
        c.run(f"rm -rf ./{short}")
        c.run(
            "video2hls "
            "--hls-type fmp4 "
            f"--hls-playlist-prefix {short}/ "
            "--audio-separate "
            "--poster-grayscale --poster-quality 70 "
            f"{video_arguments[video]} -- {video}",
            hide=False,
        )
        # Copy poster, index.m3u8, and chapters if any
        c.run(f"cp {short}/poster.jpg ../images/posters/{short}.jpg")
        c.run(f"cp {short}/index.m3u8 {short}.m3u8")
        if os.path.isfile(f"content/media/videos/{short}/chapters.vtt"):
            c.run(f"cp {short}/chapters.vtt {short}.chapters.vtt")


# When possible, normalize videos to -2.0dB for peaks. Use the
# following command to get the peak volume:
#  ffmpeg -loglevel info -i 2021-network-cmdb.mkv -af "volumedetect" -vn -sn -dn -f null /dev/null
#
# Then, to normalize (where 6.4dB is the desired offset compared to max)
#  ffmpeg -i 2021-network-cmdb.mkv -filter:a "volume=6.4dB" -c:v copy normalized.mkv


@task
def video_analyze(c, video):
    """Report the size breakdown of an encoded video."""
    directory = os.path.join("content/media/videos", os.path.splitext(video)[0])
    master = os.path.join(directory, "index.m3u8")
    if not os.path.isfile(master):
        raise Exit(f"{master} does not exist")

    def value(line, key):
        """Value of one attribute of an M3U8 tag."""
        match = re.search(f'{key}="?([^",]*)', line)
        return match and match.group(1)

    def measure(name, paths, duration):
        """Print the sizes for a set of files, return total and details."""
        # For MPEG-TS, the number of bytes taken by each PID
        pids = {}
        if paths[0].endswith(".ts"):
            for path in paths:
                with open(path, "rb") as f:
                    data = f.read()
                for high, low in zip(data[1::188], data[2::188]):
                    pid = ((high & 0x1F) << 8) | low
                    pids[pid] = pids.get(pid, 0) + 188
        # The size of each elementary stream. There are too many
        # packets to bring them back to Python, so awk adds them up.
        files = " ".join(shlex.quote(path) for path in paths)
        output = c.run(
            f"cat {files} | ffprobe -v error -of compact=p=0 "
            "-show_entries packet=stream_index,size - "
            "| awk -F'[=|]' '{ s[$2] += $4 } END { for (i in s) print i, s[i] }'",
            hide=True,
        ).stdout
        payloads = {
            int(index): int(size)
            for index, size in (line.split() for line in output.splitlines())
        }
        # The first file describes the streams. For fragmented MP4,
        # this is the initialization segment.
        streams = json.loads(
            c.run(
                "ffprobe -v error -of json "
                f"-show_entries stream=index,id,codec_type {shlex.quote(paths[0])}",
                hide=True,
            ).stdout
        )["streams"]
        # For each kind of stream, its payload and the space it takes
        # once packaged
        kinds = {}
        for stream in streams:
            payload = payloads.get(stream["index"], 0)
            kind = kinds.setdefault(stream["codec_type"], [0, 0])
            kind[0] += payload
            kind[1] += pids.get(int(stream.get("id", "0x0"), 16), payload)
        total = sum(os.path.getsize(path) for path in paths)
        cells = ""
        for kind in ("video", "audio"):
            if kind not in kinds:
                cells += f"{'-':>11}{'':6}"
                continue
            cells += f"{human(kinds[kind][0]):>11}"
            cells += f"{kinds[kind][0] * 8 / duration / 1000:>5.0f}k"
        rest = total - sum(kind[0] for kind in kinds.values())
        cells += f"{human(rest):>11}{100 * rest / total:>6.1f}%"
        print(f"{name:<16}{human(total):>11}{cells}")
        return total, kinds

    header = f"{'rendition':<16}{'on disk':>11}{'video':>11}{'':6}"
    header += f"{'audio':>11}{'':6}{'container':>11}{'':7}"
    print(header.rstrip())
    print("─" * len(header))

    # Renditions of the master playlist: variants and alternative audio
    lines = [line.strip() for line in open(master)]
    renditions = []
    for index, line in enumerate(lines):
        if line.startswith("#EXT-X-MEDIA:") and value(line, "URI"):
            renditions.append((value(line, "NAME") or "audio", value(line, "URI")))
        elif line.startswith("#EXT-X-STREAM-INF:"):
            renditions.append((value(line, "NAME") or "video", lines[index + 1]))

    ladder = []
    used = {"index.m3u8"}
    for name, uri in renditions:
        playlist = os.path.basename(uri)
        used.add(playlist)
        segments, duration = [], 0
        for line in open(os.path.join(directory, playlist)):
            line = line.strip()
            if line.startswith("#EXT-X-MAP:"):
                segments.append(value(line, "URI"))
            elif line.startswith("#EXTINF:"):
                duration += float(line.split(":", 1)[1].rstrip(","))
            elif line and not line.startswith("#"):
                segments.append(line)
        used.update(segments)
        if segments:
            paths = [os.path.join(directory, segment) for segment in segments]
            ladder.append(measure(name, paths, duration))

    # Standalone files, like the progressive version
    rows = list(ladder)
    leftovers = sorted(set(os.listdir(directory)) - used)
    for name in leftovers:
        if name.endswith(".mp4"):
            target = os.path.join(directory, name)
            duration = c.run(
                "ffprobe -v error -of default=nw=1:nk=1 "
                f"-show_entries format=duration {shlex.quote(target)}",
                hide=True,
            ).stdout
            rows.append(measure(name, [target], float(duration)))

    # Totals, then where the container bytes go
    total = sum(size for size, _ in rows)
    cells = ""
    for kind in ("video", "audio"):
        payload = sum(kinds.get(kind, [0])[0] for _, kinds in rows)
        cells += f"{human(payload) if payload else '-':>11}{'':6}"
    rest = total - sum(kind[0] for _, kinds in rows for kind in kinds.values())
    cells += f"{human(rest):>11}{100 * rest / total:>6.1f}%"
    print("─" * len(header))
    print(f"{'total':<16}{human(total):>11}{cells}")

    # Everything else
    print()
    for name in leftovers:
        if not name.endswith(".mp4"):
            size = os.path.getsize(os.path.join(directory, name))
            print(f"{name:<16}{human(size):>11}")
    playlists = sum(
        os.path.getsize(os.path.join(directory, name))
        for name in os.listdir(directory)
        if name.endswith(".m3u8")
    )
    print(f"{'playlists':<16}{human(playlists):>11}")
    size = sum(
        os.path.getsize(os.path.join(directory, name)) for name in os.listdir(directory)
    )
    print(f"{'directory':<16}{human(size):>11}")


@task
def video_upload(c, video=None):
    """Upload a transcoded video."""
    path = "content/media/videos"
    for directory in os.listdir(path):
        if not os.path.isfile(os.path.join(path, directory, "index.m3u8")):
            continue
        if video is not None and video != directory:
            continue
        with step(f"uploading {directory}"):
            for host in hosts:
                c.run(
                    "rsync --delete --info=progress2 -a {directory}/ {host}:"
                    "/data/webserver/media.bernat.ch/videos/{short}/".format(
                        host=host,
                        short=directory,
                        directory=os.path.join(path, directory),
                    ),
                    hide=False,
                )


@task
def fonts_update(c):
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
    with step("building Baskerville"):
        c.run("nix build .#build.baskerville")
        c.run("install -m 0644 result/*.woff2 content/media/fonts/")
        c.run("rm result")


@task
def links_check(c, remote=True):
    """Check links"""
    result = c.run(
        "nix run .#linkchecker -- -f ./linkcheckerrc {}".format(
            remote and "https://vincent.bernat.ch/" or "http://localhost:8080/",
        ),
        warn=True,
        hide=False,
    )
    if result.failed:
        links_fix(c)


@task
def links_fix(c):
    """Try to fix links"""
    fp = open("linkchecker-out.csv")
    reader = csv.DictReader(filter(lambda row: row[0] != "#", fp), delimiter=";")
    seen = {}
    for row in reader:
        if row["valid"] == "True":
            if "status: 30" not in row["warningstring"]:
                continue
            if "status: 302" in row["warningstring"]:
                continue
            if "status: 307" in row["warningstring"]:
                continue
            exceptions = [
                "https://encrypted.google.com",
                "https://youtu.be",
                "https://zsh.sourceforge.net",
            ]
            if any(row["urlname"].startswith(exc) for exc in exceptions):
                continue
            if row["url"].startswith(row["urlname"]):
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
            print("""
URL:       {urlname}
Source:    {parentname}
Result:    {result}
Warning:   {warningstring}
Info:      {infostring}""".format(**row))
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
            if "Redirected" in row["warningstring"]:
                redirected = row["url"]
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
            ")|Thinkpad|Yubikey|Github|Clickhouse)' \\*.html",
            hide="out",
        )
        c.run(r"! git grep -E '\"[.](\s|$)' \*.html")
    c.run("rm -rf .final/*")
    with step("run Hyde"):
        c.run(f"{bwrap} -- hyde -x gen -c %s" % conf)
    with c.cd(".final"):
        # Remove some files
        c.run("rm media/css/common.css media/css/root.css")
        # Ensure no light-dark() is remaining in SVG files
        c.run("! find . -name '*.svg' -print0 | xargs -0 grep -qF 'light-dark('")

        with step("subset fonts"):
            c.run("""
cd ..
NIX_PATH=fonts=$PWD/.final/media/fonts
NIX_PATH=$NIX_PATH:monospace=$PWD/glyphs-monospace.txt
NIX_PATH=$NIX_PATH:regular=$PWD/glyphs-regular.txt
export NIX_PATH
nix build --impure .#build.subsetFonts
cd -
cp -r --no-preserve=mode ../result/* media/fonts/.
rm ../result
""")

        # Build index
        with step("pagefind index"):
            with c.cd(".."):
                build_pagefind(c, site=".final")

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
                    root, ext = os.path.splitext(f)
                    newname = "%s.%s%s" % (root, md5[f], ext)
                    os.rename(f".final/media/{f}", f".final/media/{newname}")
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
                            rf"\([\"',]\){media}{f}\(\1\| \),"
                            rf"\1{media}{newname}\2,"
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
                        "(find . -name '*.html'    -print0 ; "
                        " find . -name 'atom.xml'  -print0 ; "
                        " find . -name 'atom.xslt' -print0) | "
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
printf " GIF %10s %10s %10s\n" \
   $(find media/images -name '*.gif' | wc -l) \
   $(find media/images -name '*.gif.webp' | wc -l) \
   $(find media/images -name '*.gif.avif' | wc -l)
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
        c.run("git diff --find-renames=10% --stat HEAD || true", pty=True, hide=False)
        if confirm("More diff?", default=True):
            c.run(
                "env GIT_PAGER=less git diff --find-renames=10% --word-diff HEAD || true",
                pty=True,
                hide=False,
            )
        with c.cd(".."):
            c.run('git annex lock && [ -z "$(git status --porcelain)" ]')
        if confirm("Keep?", default=True):
            c.run('git commit -a -m "Autocommit"', hide=False)
        else:
            c.run("git reset --hard")
            c.run("git clean -d -f")
            raise Exit("Build rollbacked")


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
            c.run(r"""
git log --name-only --pretty=format:'%x00%cI' HEAD |
awk 'BEGIN { RS = "\0"; FS = "\n" }
     NR > 1 {
       for (i = 2; i <= NF; i++)
         if ($i != "" && !seen[$i]++) print $1, $i
     }' |
while read ts file; do
    [ -e "$file" ] || [ -L "$file" ] && touch -d "$ts" -h "$file"
done
""")

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
        f"""
for h in {" ".join(hosts)}; do
    ssh -C $h zcat -f /var/log/nginx/vincent.bernat.ch.log\\* \
      | grep -aFv atom.xml | grep -F '{pattern}';
done \
    | LANG=en_US.utf8 nix run .#goaccess -- \
          --ignore-crawlers \
          --unknowns-as-crawlers \
          --keep-last=30 \
          --http-protocol=no \
          --no-term-resolver \
          --no-ip-validation \
          --no-query-string \
          --output=goaccess.html \
          --log-format=COMBINED \
          --ignore-panel=KEYPHRASES \
          --ignore-panel=REQUESTS_STATIC \
          --ignore-panel=GEO_LOCATION \
          --sort-panel=REQUESTS,BY_VISITORS,DESC \
          --sort-panel=NOT_FOUND,BY_VISITORS,DESC \
          --sort-panel=HOSTS,BY_VISITORS,DESC \
          --sort-panel=OS,BY_VISITORS,DESC \
          --sort-panel=BROWSERS,BY_VISITORS,DESC \
          --sort-panel=REFERRERS,BY_VISITORS,DESC \
          --sort-panel=REFERRING_SITES,BY_VISITORS,DESC \
          --sort-panel=STATUS_CODES,BY_VISITORS,DESC \
    """,
        hide=False,
    )
    c.run("xdg-open goaccess.html")

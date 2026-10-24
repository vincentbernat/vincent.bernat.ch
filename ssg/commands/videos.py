"""Encode and upload videos."""

import json
import re
import shlex
from pathlib import Path

from .. import config
from ..tools import human
from . import HOSTS, Exit, command, run, step

DIRECTORY = config.CONTENT / "media" / "videos"


# Additional video2hls arguments for each video.
ARGUMENTS = {
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


# When possible, normalize videos to -2.0dB for peaks. Use the
# following command to get the peak volume:
#  ffmpeg -loglevel info -i 2021-network-cmdb.mkv -af "volumedetect" -vn -sn -dn -f null /dev/null
#
# Then, to normalize (where 6.4dB is the desired offset compared to max)
#  ffmpeg -i 2021-network-cmdb.mkv -filter:a "volume=6.4dB" -c:v copy normalized.mkv
@command("video-encode")
def encode(videos: list[str]) -> None:
    """Encode videos to HLS with video2hls. Without argument, encode the
    videos not encoded yet."""
    if videos:
        for video in videos:
            encode_one(video)
        return
    for video in ARGUMENTS:
        with step(f"encoding {video}"):
            encode_one(video, True)


def encode_one(video: str, skip_if_exists: bool = False) -> None:
    if video not in ARGUMENTS:
        raise Exit(f"unknown video {video}, add it to ARGUMENTS")
    short = Path(video).stem
    if skip_if_exists and (DIRECTORY / short).is_dir():
        return
    run(f"rm -rf ./{short}", cwd=DIRECTORY)
    run(
        "video2hls "
        "--hls-type fmp4 "
        f"--hls-playlist-prefix {short}/ "
        "--audio-separate "
        "--poster-grayscale --poster-quality 70 "
        f"{ARGUMENTS[video]} -- {video}",
        cwd=DIRECTORY,
    )
    # Copy poster, index.m3u8, and chapters if any
    run(f"cp {short}/poster.jpg ../images/posters/{short}.jpg", cwd=DIRECTORY)
    run(f"cp {short}/index.m3u8 {short}.m3u8", cwd=DIRECTORY)
    if (DIRECTORY / short / "chapters.vtt").is_file():
        run(f"cp {short}/chapters.vtt {short}.chapters.vtt", cwd=DIRECTORY)


@command("video-analyze")
def analyze(videos: list[str]) -> None:
    """Report the size breakdown of encoded videos."""
    for video in videos:
        analyze_one(video)


def analyze_one(video: str) -> None:
    directory = DIRECTORY / Path(video).stem
    master = directory / "index.m3u8"
    if not master.is_file():
        raise Exit(f"{master} does not exist")

    def value(line: str, key: str) -> str | None:
        """Value of one attribute of an M3U8 tag."""
        match = re.search(f'{key}="?([^",]*)', line)
        return match and match.group(1)

    def measure(
        name: str, paths: list[Path], duration: float
    ) -> tuple[int, dict[str, list[int]]]:
        """Print the sizes for a set of files, return total and details."""
        # For MPEG-TS, the number of bytes taken by each PID
        pids: dict[int, int] = {}
        if paths[0].suffix == ".ts":
            for path in paths:
                data = path.read_bytes()
                for high, low in zip(data[1::188], data[2::188]):
                    pid = ((high & 0x1F) << 8) | low
                    pids[pid] = pids.get(pid, 0) + 188
        # The size of each elementary stream. There are too many packets to
        # bring them back to Python, so awk adds them up.
        files = " ".join(shlex.quote(str(path)) for path in paths)
        output = run(
            f"cat {files} | ffprobe -v error -of compact=p=0 "
            "-show_entries packet=stream_index,size - "
            "| awk -F'[=|]' '{ s[$2] += $4 } END { for (i in s) print i, s[i] }'",
            capture=True,
        ).stdout
        payloads = {
            int(index): int(size)
            for index, size in (line.split() for line in output.splitlines())
        }
        # The first file describes the streams. For fragmented MP4, this is
        # the initialization segment.
        streams = json.loads(
            run(
                "ffprobe -v error -of json "
                f"-show_entries stream=index,id,codec_type {shlex.quote(str(paths[0]))}",
                capture=True,
            ).stdout
        )["streams"]
        # For each kind of stream, its payload and the space it takes once
        # packaged
        kinds: dict[str, list[int]] = {}
        for stream in streams:
            payload = payloads.get(stream["index"], 0)
            sizes = kinds.setdefault(stream["codec_type"], [0, 0])
            sizes[0] += payload
            sizes[1] += pids.get(int(stream.get("id", "0x0"), 16), payload)
        total = sum(path.stat().st_size for path in paths)
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
    lines = [line.strip() for line in master.read_text().splitlines()]
    renditions: list[tuple[str, str]] = []
    for index, line in enumerate(lines):
        if line.startswith("#EXT-X-MEDIA:") and (media := value(line, "URI")):
            renditions.append((value(line, "NAME") or "audio", media))
        elif line.startswith("#EXT-X-STREAM-INF:"):
            renditions.append((value(line, "NAME") or "video", lines[index + 1]))

    ladder = []
    used = {"index.m3u8"}
    for name, uri in renditions:
        playlist = Path(uri).name
        used.add(playlist)
        segments: list[str] = []
        duration = 0.0
        with (directory / playlist).open() as f:
            for line in f:
                line = line.strip()
                if line.startswith("#EXT-X-MAP:"):
                    if init := value(line, "URI"):
                        segments.append(init)
                elif line.startswith("#EXTINF:"):
                    duration += float(line.split(":", 1)[1].rstrip(","))
                elif line and not line.startswith("#"):
                    segments.append(line)
        used.update(segments)
        if segments:
            paths = [directory / segment for segment in segments]
            ladder.append(measure(name, paths, duration))

    # Standalone files, like the progressive version
    rows = list(ladder)
    files = list(directory.iterdir())
    leftovers = sorted({path.name for path in files} - used)
    for name in leftovers:
        if name.endswith(".mp4"):
            target = directory / name
            duration = float(
                run(
                    "ffprobe -v error -of default=nw=1:nk=1 "
                    f"-show_entries format=duration {shlex.quote(str(target))}",
                    capture=True,
                ).stdout
            )
            rows.append(measure(name, [target], duration))

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
            size = (directory / name).stat().st_size
            print(f"{name:<16}{human(size):>11}")
    playlists = sum(path.stat().st_size for path in files if path.suffix == ".m3u8")
    print(f"{'playlists':<16}{human(playlists):>11}")
    size = sum(path.stat().st_size for path in files)
    print(f"{'directory':<16}{human(size):>11}")


@command("video-upload")
def upload(videos: list[str]) -> None:
    """Upload transcoded videos. Without argument, upload all of them."""
    for directory in DIRECTORY.iterdir():
        if not (directory / "index.m3u8").is_file():
            continue
        if videos and directory.name not in videos:
            continue
        with step(f"uploading {directory.name}"):
            for host in HOSTS["media"]:
                run(
                    f"rsync --delete --info=progress2 -a {directory}/ "
                    f"{host}:/data/webserver/media.bernat.ch/videos/{directory.name}/"
                )

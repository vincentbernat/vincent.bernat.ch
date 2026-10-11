"""Optimized images (production only)."""

import os
import shutil
import subprocess
from pathlib import Path

from .. import deps
from ..tools import ProcessHelper, run


def image(raw: Path, target: Path) -> list[Path | str]:
    """Write an optimized version of raw image to target. Also write AVIF or
    WebP versions when they are small enough. Return the written files."""
    os.makedirs(os.path.dirname(target), exist_ok=True)
    for path in (target, f"{target}.avif", f"{target}.webp"):
        if os.path.lexists(path):
            os.unlink(path)
    kind = os.path.splitext(target)[1]
    outputs: list[Path | str] = [target]
    alternative = None
    match kind:
        case ".svg":
            with open(raw, "rb") as f:
                interactive = b"<script" in f.read()
            if interactive:
                shutil.copyfile(raw, target)
            else:
                run(
                    "svgo",
                    "--config",
                    Path(__file__).parent / "svgo.config.js",
                    "-i",
                    raw,
                    "-o",
                    target,
                )
        case ".jpg":
            # Convert to sRGB, encode AVIF from it, then optimize the JPEG. For
            # progressive rendering of AVIF, use two layers with a 1/8 preview:
            #   avifenc --codec aom --yuv 420 -a tune=iq --layered \
            #     --scaling-mode 1/8 -q 10 in --scaling-mode:u 1 -q:u 66 in out
            run("jpgicc", "-q100", raw, target)
            alternative = f"{target}.avif"
            run(
                "avifenc",
                "--codec",
                "aom",
                "--yuv",
                "420",
                "-q",
                "66",
                "-a",
                "tune=iq",
                target,
                alternative,
            )
            run("cjpegli", target, f"{target}.tmp", "--quiet", "-d", "2.0")
            os.replace(f"{target}.tmp", target)
            tag_srgb(target)
        case ".png":
            # Exit code 98 when the result would be larger
            deps.tool("pngquant")
            result = subprocess.run(
                ["pngquant", "--skip-if-larger", "--strip", "--quiet"]
                + ["-o", target, raw],
                capture_output=True,
                check=False,
                text=True,
            )
            if result.returncode == 98:
                shutil.copyfile(raw, target)
            elif result.returncode != 0:
                raise RuntimeError(f"pngquant failed on {raw}:\n{result.stderr}")
            else:
                alternative = f"{target}.webp"
                run("cwebp", "-quiet", "-z", "8", target, "-o", alternative)
                tag_srgb(alternative)
        case ".gif":
            alternative = f"{target}.webp"
            run("gif2webp", "-quiet", raw, "-o", alternative)
            run("gifsicle", "--optimize=3", raw, "-o", target)
            tag_srgb(alternative)
        case _:
            shutil.copyfile(raw, target)
    # Prefer the original format when the alternative is not smaller enough:
    # JPEG and PNG decode fast and progressively.
    if alternative is not None:
        if os.path.getsize(target) * 0.90 > os.path.getsize(alternative):
            outputs.append(alternative)
        else:
            os.unlink(alternative)
    return outputs


# Exiftool starts slowly. It keeps running and reads one argument per line.
# Each command ends with "-execute1".
exiftool = ProcessHelper(
    "exiftool", "-stay_open", "True", "-@", "-", quit="-stay_open\nFalse\n"
)


def tag_srgb(path: Path | str) -> None:
    """Tag as sRGB, as Firefox only manages colors of tagged images."""
    deps.tool("exiftool")
    profile = deps.getenv("SRGB_PROFILE")
    args = ["-q", "-overwrite_original", f"-icc_profile<={profile}", path]
    args += ["-echo3", "status=${status}", "-execute1"]
    exiftool.send("".join(f"{arg}\n" for arg in args))
    output: list[str] = []
    while (line := exiftool.readline()) != "{ready1}\n":
        output.append(line)
    errors = exiftool.errors()
    if output[-1:] != ["status=0\n"]:
        raise RuntimeError(f"exiftool failed on {path}:\n{errors}{''.join(output)}")

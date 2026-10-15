"""Optimized images (production only)."""

import shutil
import subprocess
from pathlib import Path

from .. import deps
from ..tools import ProcessHelper, run


def image(raw: Path, target: Path) -> list[Path]:
    """Write an optimized version of raw image to target. Also write AVIF or
    WebP versions when they are small enough. Return the written files."""
    target.parent.mkdir(parents=True, exist_ok=True)
    for path in (target, Path(f"{target}.avif"), Path(f"{target}.webp")):
        path.unlink(missing_ok=True)
    outputs = [target]
    alternative = None
    match target.suffix:
        case ".svg":
            if b"<script" in raw.read_bytes():
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
            alternative = Path(f"{target}.avif")
            run(
                "avifenc",
                "--codec",
                "aom",
                "--yuv",
                "444",
                "-q",
                "66",
                "-a",
                "tune=iq",
                target,
                alternative,
            )
            run("cjpegli", target, f"{target}.tmp", "--quiet", "-d", "2.0")
            Path(f"{target}.tmp").replace(target)
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
                alternative = Path(f"{target}.webp")
                run("cwebp", "-quiet", "-z", "8", target, "-o", alternative)
                tag_srgb(alternative)
        case ".gif":
            alternative = Path(f"{target}.webp")
            run("gif2webp", "-quiet", raw, "-o", alternative)
            run("gifsicle", "--optimize=3", raw, "-o", target)
            tag_srgb(alternative)
        case _:
            shutil.copyfile(raw, target)
    # Prefer the original format when the alternative is not smaller enough:
    # JPEG and PNG decode fast and progressively.
    if alternative is not None:
        if target.stat().st_size * 0.90 > alternative.stat().st_size:
            outputs.append(alternative)
        else:
            alternative.unlink()
    return outputs


# Exiftool starts slowly. It keeps running and reads one argument per line.
# Each command ends with "-execute1".
exiftool = ProcessHelper("exiftool", "-stay_open", "True", "-@", "-")


def tag_srgb(path: Path) -> None:
    """Tag as sRGB, as Firefox only manages colors of tagged images."""
    deps.tool("exiftool")
    profile = deps.getenv("SRGB_PROFILE")
    args = ["-q", "-overwrite_original", f"-icc_profile<={profile}", path]
    args += ["-echo3", "status=${status}", "-execute1"]
    output: list[str] = []
    with exiftool:
        exiftool.send("".join(f"{arg}\n" for arg in args))
        while (line := exiftool.readline()) != "{ready1}\n":
            output.append(line)
        errors = exiftool.errors()
    if output[-1:] != ["status=0\n"]:
        raise RuntimeError(f"exiftool failed on {path}:\n{errors}{''.join(output)}")

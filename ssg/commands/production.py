"""Build, review and deploy the production site."""

import os
import shutil
import stat
import sys
from pathlib import Path

from .. import config
from . import FINAL, HOSTS, Exit, command, confirm, run, step


@command(depends=["checks"])
def build() -> None:
    """Build for production, review changes and commit them."""
    if run("git status --porcelain", cwd=FINAL, capture=True).stdout:
        raise Exit(f"{FINAL} has uncommitted changes")
    # The build changes the cache through an overlay. The changes are merged
    # if the result is kept.
    discard()
    (config.STAGING / "upper").mkdir(parents=True)
    (config.STAGING / "work").mkdir()
    try:
        with step("build"):
            run(f"SSG_STAGING=1 {sys.executable} -m doit mode=prod", cwd=config.ROOT)
        run("git add *", cwd=FINAL)
        run("git diff --find-renames=10% --stat HEAD || true", cwd=FINAL)
        if confirm("More diff?", default=True):
            run(
                "env GIT_PAGER=less git diff --find-renames=10% --word-diff HEAD || true",
                cwd=FINAL,
            )
        run('git annex lock && [ -z "$(git status --porcelain)" ]', cwd=config.ROOT)
        keep = confirm("Keep?", default=True)
    except BaseException:
        rollback()
        raise
    if not keep:
        rollback()
        raise Exit("Build rollbacked")
    merge(config.STAGING / "upper", config.MODES["production"].cache)
    discard()
    run(
        '[ -z "$(git status --porcelain)" ] || git commit -a -m "Autocommit"',
        cwd=FINAL,
    )


def rollback() -> None:
    """Restore the last committed build and drop the cache changes."""
    run("git reset --hard", cwd=FINAL)
    run("git clean -d -f", cwd=FINAL)
    discard()


def merge(upper: Path, lower: Path) -> None:
    """Apply the changes recorded in the upper directory of an overlay."""
    # The database goes last. If the merge stops, it does not describe files
    # which are not there.
    entries = sorted(upper.iterdir(), key=lambda e: e.name.startswith("doit.db"))
    for entry in entries:
        target = lower / entry.name
        st = entry.lstat()
        replaced = opaque(entry)
        if stat.S_ISCHR(st.st_mode) and st.st_rdev == 0:
            # Deleted file or directory
            remove(target)
        elif not entry.is_dir(follow_symlinks=False) or replaced or not target.is_dir():
            remove(target)
            entry.rename(target)
            if replaced:
                os.removexattr(target, "user.overlay.opaque")
        else:
            merge(entry, target)


def opaque(path: Path) -> bool:
    try:
        return os.getxattr(path, "user.overlay.opaque") == b"y"
    except OSError:
        return False


def remove(path: Path) -> None:
    if path.is_dir(follow_symlinks=False):
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def discard() -> None:
    """Remove the staging directory."""
    # The kernel leaves a directory without permissions in the work directory
    work = config.STAGING / "work" / "work"
    if work.exists():
        work.chmod(0o700)
    if config.STAGING.exists():
        shutil.rmtree(config.STAGING)


def commit_times() -> dict[str, int]:
    """Time of the last commit of each file in the production build."""
    log = run(
        "git -c core.quotePath=false log --no-renames --name-only --format=%x00%ct",
        cwd=FINAL,
        capture=True,
    ).stdout
    times: dict[str, int] = {}
    for commit in log.split("\0")[1:]:
        ts, _, names = commit.partition("\n")
        for name in names.split("\n"):
            if name:
                times.setdefault(name, int(ts))
    return times


@command()
def push(clean: bool = False) -> None:
    """Push built site to production."""
    with step("push to GitHub"):
        run("git push github", cwd=config.ROOT)

    # Restore timestamps (this relies on us not truncating history too often)
    with step("restore timestamps"):
        for name, ts in commit_times().items():
            path = FINAL / name
            if path.exists(follow_symlinks=False):
                os.utime(path, (ts, ts), follow_symlinks=False)

    for host in HOSTS["media"]:
        with step(f"push media to {host}"):
            run(
                "rsync --exclude=.git --copy-unsafe-links -rt "
                f"media/ {host}:/data/webserver/media.bernat.ch/",
                cwd=FINAL,
            )

    for host in HOSTS["www"]:
        with step(f"push HTML to {host}"):
            run(
                "rsync --exclude=.git --exclude=media --exclude=/bundle-sizes.txt "
                "--delete-delay --copy-unsafe-links -rt "
                f"./ {host}:/data/webserver/vincent.bernat.ch/",
                cwd=FINAL,
            )
            run(f"ssh {host} sudo systemctl reload caddy")

    if clean:
        for host in HOSTS["media"]:
            with step(f"clean files on {host}"):
                run(
                    "rsync --exclude=.git --copy-unsafe-links -rt "
                    "--delete-delay "
                    "--include='**/' "
                    "--include='*.avif' --include='*.webp' "
                    "--exclude='*' "
                    f"media/images {host}:/data/webserver/media.bernat.ch/",
                    cwd=FINAL,
                )
                run(
                    "rsync --exclude=.git --copy-unsafe-links -rt "
                    "--delete-delay --exclude=videos/\\*/ "
                    f"media/ {host}:/data/webserver/media.bernat.ch/",
                    cwd=FINAL,
                )


@command()
def prune_final(before: str = "1 year ago") -> None:
    """Prune old commits from final render."""
    out = run(
        f"git log --before='{before}' --pretty=format:%H | head -1",
        cwd=FINAL,
        capture=True,
    ).stdout.strip()
    assert out != ""
    run(f"echo {out} > .git/shallow", cwd=FINAL)
    run("git gc --prune=now", cwd=FINAL)


@command()
def fonts_update(names: list[str]) -> None:
    """Build fonts with Nix. Without argument, build all of them."""
    # We can compare the metrics using http://webfont-test.com/
    fonts = config.CONTENT / "media" / "fonts"
    for name in names or ("iosevka", "literata", "baskerville"):
        with step(f"building {name}"):
            run(f"nix build .#build.{name}", cwd=config.ROOT)
            run(f"install -m 0644 result/*.woff2 {fonts}/", cwd=config.ROOT)
            run("rm result", cwd=config.ROOT)

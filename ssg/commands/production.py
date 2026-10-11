"""Build, review and deploy the production site."""

import os
import shutil
import stat
import sys

from .. import config
from . import FINAL, HOSTS, Exit, confirm, run, step
from .check import check


def publish():
    """Check content, build for production, review changes and commit
    them."""
    if run("git status --porcelain", cwd=FINAL, capture=True).stdout:
        raise Exit(f"{FINAL} has uncommitted changes")
    check()
    # The build changes the cache through an overlay. The changes are merged
    # if the result is kept.
    discard()
    (config.STAGING / "upper").mkdir(parents=True)
    (config.STAGING / "work").mkdir()
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
    if confirm("Keep?", default=True):
        merge(config.STAGING / "upper", config.MODES["production"].cache)
        discard()
        run(
            '[ -z "$(git status --porcelain)" ] || git commit -a -m "Autocommit"',
            cwd=FINAL,
        )
    else:
        run("git reset --hard", cwd=FINAL)
        run("git clean -d -f", cwd=FINAL)
        discard()
        raise Exit("Build rollbacked")


def merge(upper, lower):
    """Apply the changes recorded in the upper directory of an overlay."""
    # The database goes last. If the merge stops, it does not describe files
    # which are not there.
    entries = sorted(os.scandir(upper), key=lambda e: e.name.startswith("doit.db"))
    for entry in entries:
        target = os.path.join(lower, entry.name)
        st = entry.stat(follow_symlinks=False)
        replaced = opaque(entry.path)
        if stat.S_ISCHR(st.st_mode) and st.st_rdev == 0:
            # Deleted file or directory
            remove(target)
        elif (
            not entry.is_dir(follow_symlinks=False)
            or replaced
            or not os.path.isdir(target)
        ):
            remove(target)
            os.rename(entry.path, target)
            if replaced:
                os.removexattr(target, "user.overlay.opaque")
        else:
            merge(entry.path, target)


def opaque(path):
    try:
        return os.getxattr(path, "user.overlay.opaque") == b"y"
    except OSError:
        return False


def remove(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    elif os.path.lexists(path):
        os.unlink(path)


def discard():
    """Remove the staging directory."""
    # The kernel leaves a directory without permissions in the work directory
    work = config.STAGING / "work" / "work"
    if work.exists():
        work.chmod(0o700)
    if config.STAGING.exists():
        shutil.rmtree(config.STAGING)


def push(clean=False):
    """Push built site to production."""
    with step("push to GitHub"):
        run("git push github", cwd=config.ROOT)

    # Restore timestamps (this relies on us not truncating history too often)
    with step("restore timestamps"):
        run(
            r"""
git log --name-only --pretty=format:'%x00%cI' HEAD |
awk 'BEGIN { RS = "\0"; FS = "\n" }
     NR > 1 {
       for (i = 2; i <= NF; i++)
         if ($i != "" && !seen[$i]++) print $1, $i
     }' |
while read ts file; do
    [ -e "$file" ] || [ -L "$file" ] && touch -d "$ts" -h "$file"
done
""",
            cwd=FINAL,
        )

    for host in HOSTS:
        with step(f"push media to {host}"):
            run(
                "rsync --exclude=.git --copy-unsafe-links -rt "
                f"media/ {host}:/data/webserver/media.bernat.ch/",
                cwd=FINAL,
            )

    for host in HOSTS:
        with step(f"push HTML to {host}"):
            run(
                "rsync --exclude=.git --exclude=media --exclude=/bundle-sizes.txt "
                "--delete-delay --copy-unsafe-links -rt "
                f"./ {host}:/data/webserver/vincent.bernat.ch/",
                cwd=FINAL,
            )
            run(f"ssh {host} sudo systemctl reload nginx")

    if clean:
        for host in HOSTS:
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


def prune_final(before="1 year ago"):
    """Prune old commits from final render."""
    out = run(
        f"git log --before='{before}' --pretty=format:%H | head -1",
        cwd=FINAL,
        capture=True,
    ).stdout.strip()
    assert out != ""
    run(f"echo {out} > .git/shallow", cwd=FINAL)
    run("git gc --prune=now", cwd=FINAL)


def fonts_update():
    """Build fonts with Nix."""
    # We can compare the metrics using http://webfont-test.com/
    fonts = config.CONTENT / "media" / "fonts"
    with step("building Iosevka"):
        run("nix build .#build.iosevka", cwd=config.ROOT)
        run(
            "install -m 0644 result/Iosevka*.woff2 "
            f"{fonts}/iosevka-custom-regular.woff2",
            cwd=config.ROOT,
        )
        run("rm result", cwd=config.ROOT)
    for name in ("literata", "baskerville"):
        with step(f"building {name.capitalize()}"):
            run(f"nix build .#build.{name}", cwd=config.ROOT)
            run(f"install -m 0644 result/*.woff2 {fonts}/", cwd=config.ROOT)
            run("rm result", cwd=config.ROOT)

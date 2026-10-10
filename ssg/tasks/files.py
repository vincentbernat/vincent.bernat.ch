"""Copy files, remove obsolete ones."""

import os
import shutil
import sys


def symlink(source, target):
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if os.path.lexists(target):
        os.unlink(target)
    os.symlink(source, target)


def is_symlink(source, target):
    try:
        return os.readlink(target) == str(source)
    except OSError:
        return False


def copy(source, target):
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if os.path.lexists(target):
        os.unlink(target)
    shutil.copyfile(source, target)


def prune(builder):
    """Remove files from the output directory not produced by this build."""
    out = str(builder.out)
    expected = builder.expected()
    kept = {os.path.join(out, ".git"), os.path.join(out, "media", "pagefind")}
    directories = []
    for directory, dirnames, filenames in os.walk(out):
        dirnames[:] = [d for d in dirnames if os.path.join(directory, d) not in kept]
        directories.append(directory)
        for name in filenames:
            path = os.path.join(directory, name)
            if path not in expected:
                print(f"remove {os.path.relpath(path, out)}", file=sys.stderr)
                os.unlink(path)
    for directory in reversed(directories[1:]):
        if not os.listdir(directory):
            os.rmdir(directory)

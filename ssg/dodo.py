"""Tasks to build and publish the site.

    doit                  # development build (in .out)
    doit mode=prod        # production build (in .final)
    doit serve            # serve development build
    doit build push       # check, build for production, review, commit and push
    doit list             # other commands
    doit profile=true     # profile the build (in one process)

The build runs in a sandbox, in parallel. "doit list --all" displays the build
tasks.
"""

import os
import sys
from pathlib import Path

# doit puts this directory first in sys.path. Modules here would hide modules
# with the same name, like html or markdown.
HERE = Path(__file__).resolve().parent
ROOT = str(HERE.parent)
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != HERE]
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import atexit
import cProfile
import multiprocessing
import shutil
from collections.abc import Iterator
from typing import Any

from doit import get_var

from ssg import commands, config, deps, lexers

MODE = config.MODES["production" if get_var("mode") == "prod" else "development"]
PROFILE = get_var("profile") == "true"


def sandbox() -> None:
    """Run doit again in a sandbox."""
    if shutil.which("bwrap") is None:
        sys.exit("bwrap not found, enter the development shell with nix develop")
    home = str(Path.home())
    matplotlib = Path.home() / ".cache" / "matplotlib"
    matplotlib.mkdir(parents=True, exist_ok=True)
    # Firefox, to render covers, may come from the home directory
    path = os.environ["PATH"]
    if firefox := shutil.which("firefox"):
        path = f"{Path(firefox).resolve().parent}:{path}"
    args = [
        "bwrap",
        "--ro-bind", "/usr", "/usr",
        "--tmpfs", "/usr/share/fontconfig",
        "--ro-bind", "/nix", "/nix",
        "--symlink", "usr/lib64", "/lib64",
        "--symlink", "usr/lib", "/lib",
        "--symlink", "usr/bin", "/bin",
        "--dev", "/dev",
        "--proc", "/proc",
        "--tmpfs", "/run",
        "--tmpfs", "/tmp",
        "--tmpfs", "/var/tmp",
        "--tmpfs", home,
        "--ro-bind-try", f"{home}/.config/nix", f"{home}/.config/nix",
        "--bind", ROOT, ROOT,
        "--bind", str(matplotlib), str(matplotlib),
        "--chdir", ROOT,
        "--unshare-all",
        "--die-with-parent",
        "--setenv", "SSG_SANDBOX", "1",
        "--setenv", "PATH", path,
    ]  # fmt: skip
    if MODE.production and os.environ.get("SSG_STAGING"):
        # Changes to the cache go to the staging directory
        cache = str(MODE.cache)
        upper = str(config.STAGING / "upper")
        work = str(config.STAGING / "work")
        MODE.cache.mkdir(parents=True, exist_ok=True)
        args += ["--overlay-src", cache, "--overlay", upper, work, cache]
    args += ["--", sys.executable, "-m", "doit", *sys.argv[1:]]
    os.nice(10)
    os.execvp(args[0], args)


def task_site() -> Iterator[dict[str, Any]]:
    """build tasks (doit list --all)"""
    if interactive:
        # Commands build the site in another process when needed
        return
    if listing:
        from ssg.tasks import summary

        yield from summary(MODE.production)
        return
    from ssg.model.site import Site
    from ssg.tasks.builder import Builder

    yield from Builder(Site(MODE)).tasks()


TASKS = commands.tasks()
globals().update({f"task_{name}": creator for name, creator in TASKS.items()})
COMMANDS = set(TASKS)
# The first word which is neither an option nor a variable
words = [arg for arg in sys.argv[1:] if not arg.startswith("-") and "=" not in arg]
interactive = bool(words) and words[0].partition(":")[0] in COMMANDS
listing = (
    len(sys.argv) == 4 and sys.argv[1:3] == ["list", "--template"]
    or len(sys.argv) == 2 and sys.argv[1] == "list"
)  # fmt: skip
if not interactive and not listing and not os.environ.get("SSG_SANDBOX"):
    sandbox()


def profile() -> None:
    """Profile this process until it exits."""
    profiler = cProfile.Profile()
    path = MODE.cache / "profile.prof"

    def stop() -> None:
        profiler.disable()
        profiler.dump_stats(path)
        print(f"profile written to {path}", file=sys.stderr)

    atexit.register(stop)
    profiler.enable()


if PROFILE:
    profile()


# Workers inherit the loaded site (Python 3.14 now defaults to forkserver)
multiprocessing.set_start_method("fork", force=True)

lexers.register()
MODE.cache.mkdir(parents=True, exist_ok=True)
# One worker per CPU or per 1 GiB of available memory (free memory and
# cache), whichever is lower
MEMORY = next(
    int(line.split()[1]) * 1024
    for line in Path("/proc/meminfo").read_text().splitlines()
    if line.startswith("MemAvailable:")
)
WORKERS = max(1, min(os.cpu_count() or 1, MEMORY // 2**30))
DOIT_CONFIG = {
    "dep_file": str(MODE.cache / ("serve.db" if words[:1] == ["serve"] else "doit.db")),
    "backend": "sqlite3",
    "check_file_uptodate": deps.XXHashChecker,
    # Commands may be interactive and the profiler only sees this process
    "num_process": 0 if interactive or PROFILE else WORKERS,
    "par_type": "process",
    "reporter": "executed-only",
    "default_tasks": ["prune", "pagefind"] if MODE.production else ["prune"],
}

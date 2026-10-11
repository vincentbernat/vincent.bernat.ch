"""Tasks to build and publish the site.

    doit                  # development build (in .out)
    doit mode=prod        # production build (in .final)
    doit serve            # serve development build
    doit publish          # check, build for production, review and commit
    doit push             # deploy production build
    doit list             # other commands
    doit profile=true     # profile the build (in one process)

The build runs in a sandbox, in parallel. "doit list --all" displays the build
tasks.
"""

import os
import sys

# doit puts this directory first in sys.path. Modules here would hide modules
# with the same name, like html or markdown.
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != HERE]
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import atexit
import cProfile
import multiprocessing
import shutil
from collections.abc import Callable, Iterator
from typing import Any

from doit import get_var
from doit.exceptions import TaskFailed

from ssg import commands, config, lexers
from ssg.commands import check, links, production, videos

MODE = config.MODES["production" if get_var("mode") == "prod" else "development"]
PROFILE = get_var("profile") == "true"


def sandbox() -> None:
    """Run doit again in a sandbox."""
    if shutil.which("bwrap") is None:
        sys.exit("bwrap not found, enter the development shell with nix develop")
    home = os.path.expanduser("~")
    matplotlib = os.path.join(home, ".cache", "matplotlib")
    os.makedirs(matplotlib, exist_ok=True)
    # Firefox, to render covers, may come from the home directory
    path = os.environ["PATH"]
    if firefox := shutil.which("firefox"):
        path = f"{os.path.dirname(os.path.realpath(firefox))}:{path}"
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
        "--bind", matplotlib, matplotlib,
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
    os.execvp(args[0], args)


def command(function: Callable[..., object], **task: Any) -> dict[str, Any]:
    """Task running a command."""

    def action(**kwargs: Any) -> Any:
        try:
            function(**kwargs)
        except commands.Exit as e:
            return TaskFailed(str(e))

    return {"actions": [action], "uptodate": [False], "verbosity": 2} | task


def task_serve() -> dict[str, Any]:
    """serve development build on http://localhost:8080"""
    from ssg import serve

    return command(serve.serve)


def task_check() -> dict[str, Any]:
    """check content for mistakes"""
    return command(
        check.check,
        params=[{"name": "fix", "long": "fix", "type": bool, "default": False}],
    )


def task_lint() -> dict[str, Any]:
    """check code with ruff and mypy"""
    return command(check.lint)


def task_publish() -> dict[str, Any]:
    """check, build for production, review and commit"""
    return command(production.publish)


def task_push() -> dict[str, Any]:
    """push production build"""
    return command(
        production.push,
        params=[{"name": "clean", "long": "clean", "type": bool, "default": False}],
    )


def task_prune_final() -> dict[str, Any]:
    """prune old commits from production build"""
    return command(
        production.prune_final,
        params=[{"name": "before", "long": "before", "default": "1 year ago"}],
    )


def task_fonts_update() -> dict[str, Any]:
    """build fonts with Nix"""
    return command(production.fonts_update)


def task_video_encode() -> dict[str, Any]:
    """encode videos to HLS (all if none given)"""
    return command(videos.encode, pos_arg="videos")


def task_video_analyze() -> dict[str, Any]:
    """report size breakdown of encoded videos"""
    return command(videos.analyze, pos_arg="videos")


def task_video_upload() -> dict[str, Any]:
    """upload transcoded videos (all if none given)"""
    return command(videos.upload, pos_arg="videos")


def task_links_check() -> dict[str, Any]:
    """check links"""
    return command(
        links.check,
        params=[{"name": "local", "long": "local", "type": bool, "default": False}],
    )


def task_links_fix() -> dict[str, Any]:
    """try to fix links"""
    return command(links.fix)


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


COMMANDS = {
    name.removeprefix("task_")
    for name in list(globals())
    if name.startswith("task_") and name != "task_site"
}
# The first word which is neither an option nor a variable
words = [arg for arg in sys.argv[1:] if not arg.startswith("-") and "=" not in arg]
interactive = bool(words) and words[0] in COMMANDS
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


# Workers inherit the loaded site
multiprocessing.set_start_method("fork", force=True)
lexers.register()
MODE.cache.mkdir(parents=True, exist_ok=True)
DOIT_CONFIG = {
    "dep_file": str(MODE.cache / "doit.db"),
    "backend": "sqlite3",
    # Commands may be interactive and the profiler only sees this process
    "num_process": 0 if interactive or PROFILE else os.cpu_count(),
    "par_type": "process",
    "reporter": "executed-only",
    "default_tasks": ["prune", "pagefind"] if MODE.production else ["prune"],
}

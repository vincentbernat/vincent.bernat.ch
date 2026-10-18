"""Development server: nginx serves the development build, rebuilt each time a
source file changes."""

# This does not use "doit auto" from the doit-auto1 plugin since it looks
# unmaintained (no commit since 2022). It also needs pyinotify, which is also
# unmaintained (not working on Python 3.14).

import ctypes
import os
import re
import select
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .. import config
from . import command

WATCHED = (config.CONTENT, config.LAYOUT, config.ROOT / "ssg")
NIX_PROFILES = next(
    (d for d in (config.ROOT / ".direnv~", config.ROOT / ".direnv") if d.is_dir()),
    config.ROOT / ".direnv",
)
COLORS = {"build": "\033[36m", "nginx": "\033[35m"}
RESET = "\033[0m"

# Port for reload events, nginx proxies /_reload to it
RELOAD_PORT = 8081

# From linux/inotify.h
IN_CLOSE_WRITE = 0x00000008
IN_MOVED_FROM = 0x00000040
IN_MOVED_TO = 0x00000080
IN_CREATE = 0x00000100
IN_DELETE = 0x00000200
IN_Q_OVERFLOW = 0x00004000
IN_ISDIR = 0x40000000
EVENTS = IN_CLOSE_WRITE | IN_MOVED_FROM | IN_MOVED_TO | IN_CREATE | IN_DELETE
EVENT = struct.Struct("iIII")

# Editor lock and backup files, Python cache, and temporary files
IGNORED = re.compile(
    r"^\.#|~$|^__pycache__$|\.tmp\.\d+\.[0-9a-f]+$|\.tmp$|^sed[0-9A-Za-z]{6}$"
)

# Delay without changes before building, after a first change and after
# a change following a recent one
QUIET = (0.05, 1.0)


class Watcher:
    """Watch directories for changes with inotify."""

    def __init__(self, directories: Iterable[Path]) -> None:
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.fd = self.libc.inotify_init1(os.O_CLOEXEC)
        if self.fd < 0:
            raise OSError(ctypes.get_errno(), "cannot initialize inotify")
        self.directories: dict[int, Path] = {}
        # Directories where new subdirectories are watched too
        self.recursive: set[int] = set()
        self.last = float("-inf")
        for directory in directories:
            self.add(directory)

    def add(self, top: Path) -> None:
        """Watch a directory and its subdirectories."""
        if top.name == "__pycache__":
            return
        for directory, dirnames, _ in top.walk():
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            self.watch(directory, recursive=True)

    def watch(self, directory: Path, recursive: bool = False) -> None:
        """Watch a directory, without its subdirectories."""
        wd = self.libc.inotify_add_watch(self.fd, os.fsencode(directory), EVENTS)
        if wd < 0:
            error = os.strerror(ctypes.get_errno())
            print(f"cannot watch {directory}: {error}", file=sys.stderr)
            return
        self.directories[wd] = directory
        if recursive:
            self.recursive.add(wd)

    def changes(self, timeout: float) -> list[str]:
        """Wait for changes and return the changed files. When a change comes
        less than QUIET[1] after the previous one, wait until there are no more
        changes for QUIET[1]. Otherwise, wait only for QUIET[0]."""
        changed: dict[str, None] = {}
        delay = QUIET[1]
        while select.select([self.fd], [], [], timeout)[0]:
            timeout = delay if changed else 0
            names = self.read()
            if not names:
                continue
            now = time.monotonic()
            if not changed and now - self.last >= QUIET[1]:
                delay = QUIET[0]
            self.last = now
            changed |= dict.fromkeys(names)
            timeout = delay
        return list(changed)

    def read(self) -> list[str]:
        """Read pending events. Return the changed files."""
        changed = []
        data = os.read(self.fd, 65536)
        offset = 0
        while offset < len(data):
            wd, mask, _, size = EVENT.unpack_from(data, offset)
            offset += EVENT.size
            name = os.fsdecode(data[offset : offset + size].rstrip(b"\0"))
            offset += size
            if mask & IN_Q_OVERFLOW:
                changed.append("(too many events)")
                continue
            if IGNORED.search(name):
                continue
            path = self.directories[wd] / name
            changed.append(str(path.relative_to(config.ROOT)))
            if (
                wd in self.recursive
                and mask & IN_ISDIR
                and mask & (IN_CREATE | IN_MOVED_TO)
            ):
                self.add(path)
        return changed


def forward(name: str, stream: Iterable[str]) -> None:
    """Display the output of a process, with a prefix."""
    prefix = f"{COLORS[name]}{name:5}{RESET} │ "
    for line in stream:
        print(f"{prefix}{line.rstrip()}", flush=True)


def spawn(name: str, args: list[str], **kwargs: Any) -> subprocess.Popen[str]:
    process = subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        **kwargs,
    )
    threading.Thread(target=forward, args=(name, process.stdout), daemon=True).start()
    return process


class Reloader(ThreadingHTTPServer):
    """Tell browsers to reload the page after each build, with server-sent
    events."""

    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", RELOAD_PORT), ReloadHandler)
        self.condition = threading.Condition()
        self.builds = 0
        self.run = time.time_ns()

    def reload(self) -> None:
        with self.condition:
            self.builds += 1
            self.condition.notify_all()


class ReloadHandler(BaseHTTPRequestHandler):
    server: Reloader

    def do_GET(self) -> None:
        if self.path != "/_reload":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        condition = self.server.condition
        with condition:
            seen = self.server.builds
        version = f"{self.server.run}-{seen}"
        try:
            # Browsers send the last ID back when they reconnect
            if self.headers.get("Last-Event-ID", version) != version:
                self.wfile.write(b"data: reload\n\n")
            self.wfile.write(f"id: {version}\n\n".encode())
            self.wfile.flush()
            while True:
                with condition:
                    if self.server.builds == seen:
                        condition.wait(30)
                    builds = self.server.builds
                if builds != seen:
                    seen = builds
                    version = f"{self.server.run}-{seen}"
                    self.wfile.write(f"id: {version}\ndata: reload\n\n".encode())
                else:
                    # Keep the connection open
                    self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except ConnectionError:
            pass

    def log_message(self, *args: Any) -> None:
        pass


def build() -> bool:
    process = spawn(
        "build",
        [sys.executable, "-m", "doit", "prune", "pagefind"],
        cwd=config.ROOT,
        env=os.environ | {"PYTHONUNBUFFERED": "1"},
    )
    return process.wait() == 0


def status(message: str, color: int = 32) -> None:
    print(f"\033[34;1m▶ \033[{color};1m{message}\033[0m", flush=True)


def profiles() -> dict[str, str]:
    """Targets of the Nix profiles of direnv."""
    return {
        path.name: os.readlink(path)
        for path in NIX_PROFILES.glob("flake-profile-*")
        if path.is_symlink()
    }


def check() -> bool:
    """Check the new code of this command can be imported."""
    process = subprocess.run(
        [sys.executable, "-c", f"import {__name__}"], cwd=config.ROOT, check=False
    )
    return process.returncode == 0


def restart() -> None:
    """Run this command again in a new process, with the environment from
    direnv when available."""
    args = ["-m", "doit", *sys.argv[1:]]
    if os.environ.get("DIRENV_DIR"):
        os.execvp("direnv", ["direnv", "exec", str(config.ROOT), "python", *args])
    os.execv(sys.executable, [sys.executable, *args])


@command()
def serve() -> None:
    """Serve the development build on http://localhost:8080."""
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    output = config.MODES["development"].output
    watcher = Watcher(WATCHED)
    environment = None
    if os.environ.get("DIRENV_DIR") and NIX_PROFILES.is_dir():
        watcher.watch(NIX_PROFILES)
        environment = profiles()
    myself = {
        str(Path(f).relative_to(config.ROOT)) for f in (__file__, config.__file__)
    }
    restarting = False
    reloader = Reloader()
    threading.Thread(target=reloader.serve_forever, daemon=True).start()
    nginx = None
    with tempfile.TemporaryDirectory(prefix="nginx-") as run:
        (Path(run) / "mime.types").symlink_to(os.environ["NGINX_MIME_TYPES"])
        conf = Path(run) / "nginx.conf"
        try:
            first = True
            while True:
                if nginx is not None and nginx.poll() is not None:
                    status("nginx exited", 31)
                    return
                if not first:
                    changed = watcher.changes(1)
                    if not changed:
                        continue
                    if environment is not None and profiles() != environment:
                        status("environment changed", 33)
                        restarting = True
                        break
                    changed = [
                        c for c in changed if Path(c).parts[0] != NIX_PROFILES.name
                    ]
                    if not changed:
                        continue
                    names = ", ".join(changed[:3])
                    if len(changed) > 3:
                        names += f" and {len(changed) - 3} more"
                    status(f"changed: {names}", 33)
                    if myself.intersection(changed):
                        if check():
                            restarting = True
                            break
                        status("cannot restart, waiting for changes", 31)
                        continue
                first = False
                if not build():
                    status("build failed, waiting for changes", 31)
                    continue
                new = (output / "nginx.conf").read_text()
                if not conf.exists() or conf.read_text() != new:
                    conf.write_text(new)
                    if nginx is None:
                        nginx = spawn(
                            "nginx",
                            ["nginx", "-p", run, "-e", "/dev/stderr", "-c", str(conf)],
                        )
                        status("serving on http://localhost:8080")
                    else:
                        os.kill(nginx.pid, signal.SIGHUP)
                        status("nginx reloaded")
                reloader.reload()
        except KeyboardInterrupt:
            pass
        finally:
            if nginx is not None:
                nginx.terminate()
                nginx.wait()
    if restarting:
        status("restarting", 33)
        restart()

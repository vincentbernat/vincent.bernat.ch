"""Development server: nginx serves the development build, rebuilt each time a
source file changes."""

import ctypes
import os
import select
import signal
import struct
import subprocess
import sys
import tempfile
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .. import config
from . import command

WATCHED = (config.CONTENT, config.LAYOUT, config.ROOT / "ssg")
COLORS = {"build": "\033[36m", "nginx": "\033[35m"}
RESET = "\033[0m"

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

# Wait for this delay without changes before building
QUIET = 0.2


class Watcher:
    """Watch directories for changes with inotify."""

    def __init__(self, directories: Iterable[Path]) -> None:
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.fd = self.libc.inotify_init1(os.O_CLOEXEC)
        if self.fd < 0:
            raise OSError(ctypes.get_errno(), "cannot initialize inotify")
        self.directories: dict[int, str] = {}
        for directory in directories:
            self.add(directory)

    def add(self, top: str | Path) -> None:
        """Watch a directory and its subdirectories."""
        if os.path.basename(top) == "__pycache__":
            return
        for directory, dirnames, _ in os.walk(top):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            wd = self.libc.inotify_add_watch(self.fd, os.fsencode(directory), EVENTS)
            if wd < 0:
                error = os.strerror(ctypes.get_errno())
                print(f"cannot watch {directory}: {error}", file=sys.stderr)
                continue
            self.directories[wd] = directory

    def changes(self, timeout: float) -> bool:
        """Read pending events. Tell if a watched file has changed."""
        changed = False
        while select.select([self.fd], [], [], timeout)[0]:
            data = os.read(self.fd, 65536)
            offset = 0
            while offset < len(data):
                wd, mask, _, size = EVENT.unpack_from(data, offset)
                offset += EVENT.size
                name = os.fsdecode(data[offset : offset + size].rstrip(b"\0"))
                offset += size
                if mask & IN_Q_OVERFLOW:
                    changed = True
                    continue
                if name.startswith(".#") or name.endswith("~"):
                    continue
                if name == "__pycache__":
                    continue
                changed = True
                if mask & IN_ISDIR and mask & (IN_CREATE | IN_MOVED_TO):
                    self.add(os.path.join(self.directories[wd], name))
            # Wait until there are no more changes
            timeout = QUIET if changed else 0
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


@command()
def serve() -> None:
    """Serve the development build on http://localhost:8080."""
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    output = config.MODES["development"].output
    watcher = Watcher(WATCHED)
    nginx = None
    with tempfile.TemporaryDirectory(prefix="nginx-") as run:
        os.symlink(os.environ["NGINX_MIME_TYPES"], f"{run}/mime.types")
        conf = Path(run) / "nginx.conf"
        try:
            changed = True
            while True:
                if nginx is not None and nginx.poll() is not None:
                    status("nginx exited", 31)
                    return
                if not changed:
                    changed = watcher.changes(1)
                    continue
                changed = False
                if not build():
                    status("build failed, waiting for changes", 31)
                    continue
                new = (output / "nginx.conf").read_text()
                if conf.exists() and conf.read_text() == new:
                    continue
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
        except KeyboardInterrupt:
            pass
        finally:
            if nginx is not None:
                nginx.terminate()
                nginx.wait()

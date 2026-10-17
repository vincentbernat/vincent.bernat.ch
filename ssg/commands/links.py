"""Check and fix links."""

import contextlib
import csv
import datetime
import json
import re
import shlex
import sqlite3

from .. import config
from . import command, run

OUTPUT = config.ROOT / ".linkchecker-out.csv"
DATABASE = config.ROOT / ".linkchecker.db"


def results() -> tuple[list[dict[str, str]], bool]:
    """Read the results of the last run and tell if it reached the end."""
    with OUTPUT.open(encoding="utf-8") as fp:
        lines = fp.readlines()
    rows = csv.DictReader(
        (line for line in lines if not line.startswith("#")), delimiter=";"
    )
    return list(rows), any(line.startswith("# Stopped checking") for line in lines)


def database() -> sqlite3.Connection:
    """Open the database keeping the history of dead links."""
    db = sqlite3.connect(DATABASE)
    db.execute("""
CREATE TABLE IF NOT EXISTS dead (
  url TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  count INTEGER NOT NULL
)""")
    return db


def record(rows: list[dict[str, str]], complete: bool) -> None:
    """Record the dead links of the last run, forget the ones back alive."""
    today = datetime.datetime.now(datetime.UTC).date().isoformat()
    dead = {row["urlname"]: row["result"] for row in rows if row["valid"] != "True"}
    with contextlib.closing(database()) as db, db:
        if complete:
            # Only errors land in the CSV: a link missing from it is alive
            # again or gone from the content. A partial run tells nothing.
            db.execute(
                "DELETE FROM dead WHERE url NOT IN (SELECT value FROM json_each(?))",
                (json.dumps(list(dead)),),
            )
        for url, status in dead.items():
            # Checking twice the same day should not count twice.
            db.execute(
                "INSERT INTO dead (url, status, first_seen, last_seen, count) "
                "VALUES (?, ?, ?, ?, 1) "
                "ON CONFLICT (url) DO UPDATE SET "
                "  status = excluded.status, "
                "  last_seen = excluded.last_seen, "
                "  count = dead.count + 1 "
                "WHERE dead.last_seen <> excluded.last_seen",
                (url, status, today, today),
            )


def history(url: str) -> str | None:
    """Tell for how long an URL has been dead."""
    with contextlib.closing(database()) as db:
        row = db.execute(
            "SELECT first_seen, count FROM dead WHERE url = ?", (url,)
        ).fetchone()
    if row is None:
        return None
    first_seen, count = row
    times = "once" if count == 1 else f"{count} times"
    return f"dead since {first_seen}, {times}"


def replace(url: str, replacement: str) -> None:
    """Replace an URL in the content."""
    pattern = re.compile(
        rf"(?:(?<=[\s(<])|^){re.escape(url)}(?=[\s)>\"']|$)", re.MULTILINE
    )
    files = run(
        f"git grep -Fl -e {shlex.quote(url)}",
        cwd=config.ROOT,
        capture=True,
        check=False,
    )
    for name in files.stdout.split():
        path = config.ROOT / name
        content = path.read_text(encoding="utf-8")
        updated = pattern.sub(lambda _: replacement, content)
        if updated != content:
            path.write_text(updated, encoding="utf-8")


@command("links-check")
def check(local: bool = False) -> None:
    """Check links."""
    url = "http://localhost:8080/" if local else "https://vincent.bernat.ch/"
    result = run(
        f"nix run .#linkchecker -- -f ./linkcheckerrc {url}",
        cwd=config.ROOT,
        check=False,
    )
    record(*results())
    if result.returncode != 0:
        fix()


@command("links-fix")
def fix() -> None:
    """Try to fix links."""
    rows, _ = results()
    seen = set()
    for row in rows:
        if row["valid"] == "True":
            if "status: 30" not in row["warningstring"]:
                continue
            if "status: 302" in row["warningstring"]:
                continue
            if "status: 307" in row["warningstring"]:
                continue
            exceptions = [
                "https://encrypted.google.com",
                "https://youtu.be",
                "https://zsh.sourceforge.net",
            ]
            if any(row["urlname"].startswith(exc) for exc in exceptions):
                continue
            if row["url"].startswith(row["urlname"]):
                continue
        year = datetime.datetime.now(datetime.UTC).year
        mo = re.search(r"/blog/(\d+)-", row["parentname"])
        if row["urlname"] in seen:
            continue
        if mo:
            year = int(mo.group(1))
        archive = {
            "a": f"https://archive.today/{year}/{row['urlname']}",
            "w": f"https://web.archive.org/web/{year}/{row['urlname']}",
        }
        dead = history(row["urlname"])
        while True:
            print(f"""
URL:       {row["urlname"]}
Source:    {row["parentname"]}
Result:    {row["result"]}
Warning:   {row["warningstring"]}
Info:      {row["infostring"]}""")
            if dead:
                print(f"History:   {dead}")
            print(f"""
(c) Continue
(b) Browse {row["urlname"]}
(p) Browse {row["parentname"]}
(r) Replace by your own URL
(q) Quit""")
            valid = "cbprq"
            for a, archived in archive.items():
                print(f"({a}) Browse {archived}")
                print(f"({a.upper()}) Replace by {archived}")
                valid += a
                valid += a.upper()
            if "Redirected" in row["warningstring"]:
                redirected = row["url"]
                print(f"(R) Replace by {redirected}")
                valid += "R"
            print()
            ans = input("Command? ")
            if ans not in valid:
                continue
            if ans == "c":
                break
            elif ans == "q":
                return
            elif ans == "r":
                replace(row["urlname"], input("URL? "))
                break
            elif ans == "b":
                run(f"xdg-open '{row['urlname']}'")
            elif ans == "p":
                run(f"xdg-open '{row['parentname']}'")
            elif ans == "R":
                replace(row["urlname"], redirected)
                break
            else:
                found = False
                for a, archived in archive.items():
                    if ans == a:
                        run(f"xdg-open '{archived}'")
                        break
                    elif ans == a.upper():
                        replace(row["urlname"], archived)
                        found = True
                        break
                if found:
                    break
        seen.add(row["urlname"])

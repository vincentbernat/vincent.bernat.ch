"""Check and fix links."""

from .. import config
from . import command, run


@command("links-check")
def check(local: bool = False) -> None:
    """Check links."""
    run(f"tools/links check{' --local' if local else ''}", cwd=config.ROOT)


@command("links-fix")
def fix() -> None:
    """Try to fix links."""
    run("tools/links fix", cwd=config.ROOT)

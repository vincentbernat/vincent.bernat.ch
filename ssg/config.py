"""Settings of the site."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
LAYOUT = ROOT / "layout"
CACHE = ROOT / ".cache" / "ssg"
STAGING = CACHE / "staging"

BASE = "https://vincent.bernat.ch"
LANGUAGES = {"en": "English", "fr": "français"}


class Mode:
    def __init__(
        self,
        name: str,
        output: str,
        media_url: str,
        cdn: tuple[tuple[str, str], ...] = (),
    ) -> None:
        self.name = name
        self.output = ROOT / output
        self.cache = CACHE / name
        self.media_url = media_url
        # Media served from another domain, by path prefix
        self.cdn = cdn

    @property
    def production(self) -> bool:
        return self.name == "production"


MODES = {
    "development": Mode("development", ".out", "/media/"),
    "production": Mode(
        "production",
        ".final",
        "https://media-bernat-ch.b-cdn.net/",
        cdn=(
            ("files/", "https://media.bernat.ch/files/"),
            ("videos/", "https://media.bernat.ch/videos/"),
            ("pagefind/", "https://media.bernat.ch/pagefind/"),
        ),
    ),
}

# Default metadata. meta.yaml files in content/ extend it.
META = {
    "author": "Vincent Bernat",
    "mastodon": "@vincent@bernat.ch",
    "bluesky": "vincent.bernat.ch",
    "github": "vincentbernat",
    "title": "MTU Ninja | Vincent Bernat",
    "language": "en",
    "locale": "en_US",
    "share": False,
    "popular": False,
    "featured": False,
    "tags": ["unclassified"],
    "sources": "https://github.com/vincentbernat/vincent.bernat.ch",
}

# Copied as symbolic links
SIMPLE_COPY = ("media/videos/**", "media/files/**")

IGNORE = ("*~", "*.bak", ".hg", ".git", ".svn")

# Additional files to load when a selector matches
LOAD = (
    (".lf-media-outer, .lf-gallery", ["js/luffy1.rhythm.js"], False),
    (".lf-sidenote", ["css/luffy1.sidenotes.css"], False),
    (".toc", ["js/luffy1.toc.js", "css/luffy1.toc.css"], False),
    (".codehilite", ["js/luffy1.code.js", "css/luffy1.code.css"], False),
    (".lf-media", ["css/luffy1.media.css"], False),
    (
        "video.lf-media source[type='application/vnd.apple.mpegurl']",
        ["js/hls.js"],
        True,
    ),
    (
        "video.lf-media source[type='application/vnd.apple.mpegurl']",
        ["js/luffy1.videos.js"],
        False,
    ),
    (".lf-gallery", ["css/gallery.css", "js/gallery.js"], False),
    (".lf-listing", ["css/luffy1.listing.css"], False),
    ("x-latex", ["css/katex.css"], False),
)

TAGS: dict[str, dict[str, str | bool]] = {
    "network": {"descr_en": "network", "descr_fr": "réseau", "feed": True},
    "network-bgp": {"descr": "BGP"},
    "network-automation": {"descr_en": "automation", "descr_fr": "automatisation"},
    "network-monitoring": {"descr_en": "monitoring", "descr_fr": "supervision"},
    "network-vxlan": {"descr": "VXLAN"},
    "network-tls": {"descr": "TLS"},
    "network-vpn": {"descr": "VPN"},
    "network-ipv6": {"descr": "IPv6"},
    "linux": {"descr": "Linux", "feed": True},  # this means "Linux kernel"
    "programming": {"descr_en": "programming", "descr_fr": "programmation"},
    "programming-go": {"descr": "Go", "feed": True},
    "programming-c": {"descr": "C"},
    "programming-python": {"descr": "Python", "feed": True},
    "programming-shell": {"descr": "shell"},
    "project": {"descr_en": "project", "descr_fr": "projet", "hidden": True},
    "project-akvorado": {"descr": "Akvorado"},
    "distribution": {"descr": "distribution"},
    "distribution-debian": {"descr": "Debian", "feed": True},
    "distribution-nixos": {"descr": "NixOS", "feed": True},
    "retro": {"descr_en": "retrocomputing", "descr_fr": "rétrocomputing", "feed": True},
    "retro-wguide": {"descr": "W"},
    "web": {"descr": "web", "feed": True},
    "security": {"descr_en": "security", "descr_fr": "sécurité"},
    "desktop": {
        "descr_en": "desktop environment",
        "descr_fr": "environnement de bureau",
    },
    "talks": {"descr_en": "talks", "descr_fr": "présentations"},
    "unclassified": {"descr_en": "unclassified", "descr_fr": "non classé"},
    "outdated": {"descr_en": "outdated", "descr_fr": "périmé"},
}

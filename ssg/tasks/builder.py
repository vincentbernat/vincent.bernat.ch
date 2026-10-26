"""Plan the tasks to build the site."""

from __future__ import annotations

import datetime
import functools
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from doit.tools import config_changed, timeout

from .. import config, deps, fonts, templates
from ..images import covers, scales, thumbnails
from ..media import css
from . import GROUPS, SINGLES, Task, files, fingerprint, pagefind, render, sizes

if TYPE_CHECKING:
    from ..model.resource import Resource
    from ..model.site import Site

SSG = config.ROOT / "ssg"


# Modules not used by the build
NOT_BUILD = ("commands", "dodo.py")
CODE = sorted(
    str(p) for p in SSG.rglob("*.py") if p.relative_to(SSG).parts[0] not in NOT_BUILD
) + [
    str(SSG / "markdown" / "rfc-index.json.gz"),
]


CSS_DEPS = [
    str(css.SCRIPT),
    str(css.BASELINE_FONT),
] + [str(p) for p in css.SHARED]


# Pages compute image sizes from root.css
PAGE_CSS_DEPS = [
    str(css.SCRIPT),
    str(config.CONTENT / "media" / "css" / "root.css"),
]


IMAGES = SSG / "images"
SCALE_DEPS = [str(IMAGES / "__init__.py"), str(IMAGES / "scales.py")]
THUMBNAIL_DEPS = [str(IMAGES / "__init__.py"), str(IMAGES / "thumbnails.py")]
COVER_DEPS = [str(IMAGES / "covers.py"), str(IMAGES / "firefox.mjs")]
OPTIMIZE_DEPS = [str(IMAGES / "optimize.py"), str(IMAGES / "svgo.config.js")]
FAVICON = config.CONTENT / "media" / "images" / "favicon.png"


# Media directories whose files get a hashed name
HASHED = ("fonts/", "images/", "js/", "css/")


# Only used to build other stylesheets
UNFINGERPRINTED = tuple(f"css/{p.name}" for p in css.SHARED)


# Video files are served from another server
VIDEOS_KEPT = (".m3u8", ".vtt", ".txt")


class Environment(config_changed):
    """Like config_changed, but also save the configuration, to tell later
    what changed."""

    def configure_task(self, task: Any) -> None:
        super().configure_task(task)
        task.value_savers.append(lambda: {"_config": self.config})


@functools.cache
def environment(**values: str) -> Environment:
    """What a task uses from the development environment. With Nix, a new
    version of the Python environment or the node modules has a new path, and
    tasks using it run again. Tools are recorded when they run."""
    result = {
        "python": sys.prefix,
        "node_modules": str((config.ROOT / "node_modules").resolve()),
    }
    return Environment(result | values)


class Builder:
    """Generate the tasks for a site."""

    def __init__(self, site: Site) -> None:
        self.site = site
        self.mode = site.mode
        self.out = self.mode.output
        self.uptodate = deps.uptodate(site)
        deps.code_files = CODE
        deps.code_digest()
        self.plan()

    def plan(self) -> None:
        """Sort resources and find files to generate."""
        site = self.site
        production = self.mode.production
        self.pages: list[Resource] = []
        self.media: list[Resource] = []
        self.copies: list[Resource] = []
        for resource in site.content.walk_resources():
            if not resource.processable:
                continue
            if resource.simple_copy:
                if (
                    production
                    and resource.path.startswith("media/videos/")
                    and not resource.path.endswith(VIDEOS_KEPT)
                ):
                    continue
                self.copies.append(resource)
            elif resource.path.startswith("media/"):
                if not resource.media_path.startswith(HASHED):
                    raise ValueError(
                        f"{resource}: media files go in {', '.join(HASHED)}"
                    )
                self.media.append(resource)
            elif resource.text:
                self.pages.append(resource)
            else:
                self.copies.append(resource)

        # Generated media files
        generated = [r.media_path for r in self.media if r.text]
        self.fragments: dict[str, Path] = {}
        for resource in self.pages:
            layout = resource.meta.get("layout")
            if layout and not (config.LAYOUT / layout).is_file():
                raise ValueError(f"{resource}: unknown layout {layout}")
            if templates.is_article_layout(self.site, layout):
                self.fragments[resource.path] = templates.fragment_path(resource)
            if resource.kind == "html":
                generated.append(resource.cover_image())
        self.resizes = self.find_resizes()
        self.thumbs = self.find_thumbs()
        generated += [*self.resizes, *self.thumbs, "js/pagefind.js"]
        if production:
            generated += [f"fonts/{name}.woff2" for name in fonts.SUBSET]
        for path in generated:
            site.generated[path] = self.mode.cache / "media" / path

        # Media files with a hashed name
        self.fingerprinted = sorted(
            path
            for path in {r.media_path for r in self.media} | set(site.generated)
            if path.startswith(HASHED) and path not in UNFINGERPRINTED
        )

    def find_resizes(self) -> dict[str, tuple[Resource, float]]:
        """Smaller versions of images named foo@2x.jpg used in pages."""
        referenced = {}
        pattern = re.compile(r"images/[\w./@-]+@([2-9])x\.(?:jpg|png)")
        for resource in self.pages:
            for mo in pattern.finditer(resource.source_text):
                referenced[mo.group(0)] = int(mo.group(1))
        result = {}
        for path, factor in sorted(referenced.items()):
            source = self.site.resources.get(f"media/{path}")
            if source is None:
                continue
            for f, smaller in enumerate(scales.smaller(path), 1):
                if f"media/{smaller}" not in self.site.resources:
                    result[smaller] = (source, f / factor)
        return result

    def find_thumbs(self) -> dict[str, Resource]:
        """Thumbnails of images displayed in a gallery."""
        result = {}
        self.gallery_thumbs: dict[str, list[str]] = {}
        for resource in self.pages:
            for gallery in resource.meta.get("galleries") or []:
                directory = gallery.directory
                node = self.site.nodes.get(f"media/images/{directory}")
                if node is None:
                    raise ValueError(f"{resource}: unknown gallery {directory}")
                for image in node.walk_resources():
                    if image.kind in ("jpg", "png"):
                        path = thumbnails.path(image).removeprefix("media/")
                        result[path] = image
                        self.gallery_thumbs.setdefault(resource.path, []).append(path)
        return result

    def tasks(self) -> Iterator[Task]:
        """Actions record what they read, tools included. The task runs again
        when one of them changes."""
        for task in self.all_tasks():
            if "actions" in task:
                task["actions"] = [
                    (deps.recorded, [function, *args])
                    for function, args in task["actions"]
                ]
                task["uptodate"] = task.get("uptodate", []) + [self.uptodate]
            yield task

    def all_tasks(self) -> Iterator[Task]:
        for basename, (doc, production) in GROUPS.items():
            if self.mode.production or not production:
                yield {"basename": basename, "name": None, "doc": doc}
        yield from self.copy_tasks()
        yield from self.media_tasks()
        yield from self.image_tasks()
        yield from self.cover_tasks()
        yield from self.fragment_tasks()
        yield from self.page_tasks()
        yield from self.pagefind_tasks()
        yield from self.fingerprint_tasks()
        if self.mode.production:
            yield from self.font_tasks()
            yield from self.bundle_sizes_task()
        yield from self.prune_task()

    def copy_tasks(self) -> Iterator[Task]:
        for resource in self.copies:
            target = self.out / resource.path
            if resource.simple_copy:
                yield {
                    "basename": "copy",
                    "name": resource.path,
                    "actions": [(files.symlink, [resource.source, target])],
                    "targets": [str(target)],
                    "uptodate": [(files.is_symlink, [resource.source, target])],
                }
            else:
                yield {
                    "basename": "copy",
                    "name": resource.path,
                    "actions": [(files.copy, [resource.source, target])],
                    "file_dep": [str(resource.source)],
                    "targets": [str(target)],
                }

    def media_tasks(self) -> Iterator[Task]:
        for resource in self.media:
            if not resource.text:
                continue
            path = resource.media_path
            file_dep = [str(p) for p in (SSG / "media").glob("*.py")] + [
                str(resource.source)
            ]
            file_dep += [str(r.source) for r in resource.combined]
            if resource.kind == "css":
                file_dep += CSS_DEPS
            if resource.uses_template:
                file_dep += templates.page_layouts(resource)
            yield {
                "basename": "image" if resource.kind == "svg" else "media",
                "name": path,
                "actions": [(render.media, [self.site, resource])],
                "file_dep": sorted(set(file_dep)),
                "targets": [str(self.site.generated[path])],
                "uptodate": [environment()],
            }

    def image_tasks(self) -> Iterator[Task]:
        for path, (source, factor) in self.resizes.items():
            target = self.site.generated[path]
            yield {
                "basename": "image",
                "name": path,
                "actions": [(scales.resize, [source.source, target, factor])],
                "file_dep": [str(source.source)] + SCALE_DEPS,
                "targets": [str(target)],
                "uptodate": [environment()],
            }
        for path, source in self.thumbs.items():
            target = self.site.generated[path]
            yield {
                "basename": "image",
                "name": path,
                "actions": [(thumbnails.make, [source.source, target])],
                "file_dep": [str(source.source)] + THUMBNAIL_DEPS,
                "targets": [str(target)],
                "uptodate": [environment()],
            }

    def cover_tasks(self) -> Iterator[Task]:
        for resource in self.pages:
            if resource.kind != "html":
                continue
            target = self.site.generated[resource.cover_image()]
            cover = resource.meta.get("cover")
            file_dep = COVER_DEPS + [str(FAVICON)]
            if cover:
                image = self.site.resources.get(f"media/images/{cover}")
                if image is None:
                    raise ValueError(f"{resource}: unknown cover {cover}")
                cover = self.site.raw(f"images/{cover}")
                file_dep.append(str(cover))
            title, author = resource.meta.title, resource.meta.author or ""
            yield {
                "basename": "cover",
                "name": resource.path,
                "actions": [(covers.generate, [title, author, cover, target])],
                "file_dep": file_dep,
                "targets": [str(target)],
                "uptodate": [environment(title=title, author=author)],
            }

    def fragment_tasks(self) -> Iterator[Task]:
        """Render the articles. Other pages may use the articles of blog
        posts."""
        for path, target in self.fragments.items():
            resource = self.site.resources[path]
            post = resource.post
            yield {
                "basename": "article" if post else "fragment",
                "name": path,
                "actions": [(render.fragment, [self.site, resource, target])],
                "file_dep": [str(resource.source)]
                + templates.article_layouts(resource)
                + [
                    str(self.site.generated[thumb])
                    for thumb in self.gallery_thumbs.get(path, [])
                ],
                "targets": [str(target)],
                "task_dep": [] if post else ["article"],
                "uptodate": [environment()],
            }

    def page_tasks(self) -> Iterator[Task]:
        for resource in self.pages:
            target = self.out / resource.path
            fragment = self.fragments.get(resource.path)
            file_dep = [str(resource.source)] + PAGE_CSS_DEPS
            file_dep += templates.page_layouts(resource)
            if fragment:
                file_dep.append(str(fragment))
            task_dep = ["article", "image", "fingerprint-font", "fingerprint-asset"]
            if resource.kind == "html":
                task_dep.append(f"cover:{resource.path}")
            yield {
                "basename": "page",
                "name": resource.path,
                "actions": [(render.page, [self.site, resource, fragment, target])],
                "file_dep": file_dep,
                "targets": [str(target)],
                "task_dep": task_dep,
                "uptodate": [environment()],
            }

    def pagefind_tasks(self) -> Iterator[Task]:
        target = self.site.generated["js/pagefind.js"]
        yield {
            "basename": "pagefind-js",
            "doc": SINGLES["pagefind-js"][0],
            "actions": [(pagefind.extract, [target])],
            "targets": [str(target)],
            "uptodate": [environment()],
        }
        pages = [str(self.out / r.path) for r in self.pages if r.kind == "html"]
        yield {
            "basename": "pagefind",
            "doc": SINGLES["pagefind"][0],
            "actions": [(pagefind.index, [self.site])],
            "file_dep": pages,
            "task_dep": ["prune"],
            "targets": [str(self.mode.cache / "pagefind.json")],
            "uptodate": [(pagefind.exist, [self.site]), environment()],
        }

    def font_tasks(self) -> Iterator[Task]:
        fragments = list(self.fragments.values())
        yield {
            "basename": "glyphs",
            "doc": SINGLES["glyphs"][0],
            "actions": [(fonts.glyphs, [self.site, fragments])],
            "file_dep": [str(f) for f in fragments]
            + [str(SSG / "fonts.py"), str(SSG / "markdown" / "__init__.py")],
            "targets": [str(fonts.glyphs_path(self.site, k)) for k in fonts.KINDS],
            "uptodate": [environment()],
        }
        for name, (kind, _) in fonts.SUBSET.items():
            path = f"fonts/{name}.woff2"
            source = config.CONTENT / "media" / path
            target = self.site.generated[path]
            yield {
                "basename": "subset",
                "name": name,
                "actions": [(fonts.subset, [self.site, name, source, target])],
                "file_dep": [
                    str(source),
                    str(fonts.glyphs_path(self.site, kind)),
                    str(SSG / "fonts.py"),
                ],
                "targets": [str(target)],
                "uptodate": [environment()],
            }

    def fingerprint_tasks(self) -> Iterator[Task]:
        """Media files get a name with a hash of their content."""
        for path in self.fingerprinted:
            sidecar = self.site.sidecar(path)
            file_dep = [str(self.site.raw(path))]
            task_dep = []
            uptodate = [(fingerprint.exist, [self.site, path, sidecar])]
            if path.startswith("images/"):
                basename = "fingerprint-image"
                action = fingerprint.image
                file_dep += OPTIMIZE_DEPS
                uptodate.append(environment())
            elif path.startswith("fonts/"):
                basename = "fingerprint-font"
                action = fingerprint.file
            elif path.startswith("css/"):
                basename = "fingerprint-asset"
                action = fingerprint.css
                task_dep = ["image", "fingerprint-font"]
            else:
                basename = "fingerprint-asset"
                action = fingerprint.file
            yield {
                "basename": basename,
                "name": path,
                "actions": [(action, [self.site, path, sidecar])],
                "file_dep": file_dep,
                "targets": [str(sidecar)],
                "task_dep": task_dep,
                "uptodate": uptodate,
            }

    def bundle_sizes_task(self) -> Iterator[Task]:
        target = self.out / "bundle-sizes.txt"
        pages = [str(self.out / r.path) for r in self.pages if r.kind == "html"]
        bundles = [
            path
            for path in self.fingerprinted
            if path.count("/") == 1
            and path.endswith((".css", ".js", ".woff2"))
            and path.startswith(("css/", "js/", "fonts/"))
        ]
        yield {
            "basename": "bundle-sizes",
            "doc": SINGLES["bundle-sizes"][0],
            "actions": [(sizes.bundle_sizes, [self.site, bundles, target])],
            "file_dep": pages + [str(self.site.sidecar(b)) for b in bundles],
            "targets": [str(target)],
            "uptodate": [environment()],
        }

    def prune_task(self) -> Iterator[Task]:
        kinds = [
            kind
            for kind, (_, production) in (GROUPS | SINGLES).items()
            if (self.mode.production or not production)
            and kind not in ("pagefind", "prune")
        ]
        yield {
            "basename": "prune",
            "doc": SINGLES["prune"][0],
            "actions": [(files.prune, [self])],
            "task_dep": kinds,
            "uptodate": [
                False if self.mode.production else timeout(datetime.timedelta(days=1))
            ],
        }

    def expected(self) -> set[Path]:
        """Files expected in the output directory."""
        result = {self.out / r.path for r in self.copies + self.pages}
        if self.mode.production:
            result.add(self.out / "bundle-sizes.txt")
        for path in self.fingerprinted:
            try:
                names = json.loads(self.site.sidecar(path).read_text())["files"]
            except FileNotFoundError:
                continue
            result.update(self.out / "media" / f for f in names)
        return result

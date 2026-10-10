"""Plan the tasks to build the site."""

import functools
import json
import os
import re
import shutil
import sys

from doit.tools import config_changed

from .. import config, deps, fonts, templates
from ..images import covers, scales, thumbnails
from ..media import css
from . import files, pagefind, publish, render

SSG = config.ROOT / "ssg"


# Modules not used by the build
NOT_BUILD = ("commands", "dodo.py", "serve.py")
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
COVER_DEPS = [str(IMAGES / "covers.py")]
OPTIMIZE_DEPS = [str(IMAGES / "optimize.py"), str(IMAGES / "svgo.config.js")]
FAVICON = config.CONTENT / "media" / "images" / "favicon.png"


# Media directories whose files get a hashed name in production
HASHED = ("fonts/", "images/", "js/", "css/")


# Only used to build other stylesheets
UNPUBLISHED = tuple(f"css/{p.name}" for p in css.SHARED)


# Video files are served from another server
VIDEOS_KEPT = (".m3u8", ".vtt", ".txt")


# Kinds with several tasks, with their description and if they are only for
# production
GROUPS = {
    "copy": ("copy files as is", False),
    "media": ("process stylesheets, scripts and other text media", False),
    "image": ("generate images (SVG, resized images, thumbnails)", False),
    "cover": ("generate cover images", False),
    "article": ("render articles of blog posts", False),
    "fragment": ("render articles of other pages", False),
    "page": ("render pages", False),
    "subset": ("subset fonts", True),
    "font": ("publish fonts with a hashed name", True),
    "asset": ("publish stylesheets and scripts with a hashed name", True),
    "optimize": ("publish optimized images with a hashed name", True),
}


@functools.cache
def environment(*tools, variables=(), **values):
    """What a task uses from the development environment. With Nix, a new
    version of the Python environment, the node modules or a tool has a new
    path, and tasks using it run again."""
    result = {
        "python": sys.prefix,
        "node_modules": os.path.realpath(config.ROOT / "node_modules"),
    }
    result |= {tool: os.path.realpath(shutil.which(tool) or tool) for tool in tools}
    result |= {name: os.environ.get(name, "") for name in variables}
    return config_changed(result | values)


class Builder:
    """Generate the tasks for a site."""

    def __init__(self, site):
        self.site = site
        self.mode = site.mode
        self.out = self.mode.output
        self.uptodate = deps.uptodate(site)
        deps.code_files = CODE
        deps.code_digest()
        self.plan()

    def plan(self):
        """Sort resources and find files to generate."""
        site = self.site
        production = self.mode.production
        self.pages = []
        self.media = []
        self.copies = []
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
        for resource in self.media:
            if resource.text:
                site.generated[resource.media_path] = None
        self.fragments = {}
        for resource in self.pages:
            layout = resource.meta.get("layout")
            if layout and not (config.LAYOUT / layout).is_file():
                raise ValueError(f"{resource}: unknown layout {layout}")
            if templates.is_article_layout(self.site, layout):
                self.fragments[resource.path] = templates.fragment_path(resource)
            if resource.kind == "html":
                site.generated[resource.cover_image()] = None
        self.resizes = self.find_resizes()
        self.thumbs = self.find_thumbs()
        site.generated.update(dict.fromkeys(self.resizes))
        site.generated.update(dict.fromkeys(self.thumbs))
        site.generated["js/pagefind.js"] = None
        if production:
            for name in fonts.SUBSET:
                site.generated[f"fonts/{name}.woff2"] = None
        for path in site.generated:
            if production:
                site.generated[path] = self.mode.cache / "media" / path
            else:
                site.generated[path] = self.out / "media" / path

        # Media files with a hashed name in production
        self.published = sorted(
            path
            for path in {r.media_path for r in self.media} | set(site.generated)
            if path.startswith(HASHED) and path not in UNPUBLISHED
        )

    def find_resizes(self):
        """Smaller versions of images named foo@2x.jpg used in pages."""
        referenced = set()
        pattern = re.compile(r"images/[\w./@-]+@[2-9]x\.(?:jpg|png)")
        for resource in self.pages:
            referenced.update(pattern.findall(resource.content))
        result = {}
        for path in sorted(referenced):
            source = self.site.resources.get(f"media/{path}")
            if source is None:
                continue
            factor = int(scales.PATTERN.match(path).group(1))
            for f, smaller in enumerate(scales.smaller(path), 1):
                if f"media/{smaller}" not in self.site.resources:
                    result[smaller] = (source, f / factor)
        return result

    def find_thumbs(self):
        """Thumbnails of images displayed in a gallery."""
        result = {}
        self.gallery_thumbs = {}
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

    def tasks(self):
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
        if self.mode.production:
            yield from self.font_tasks()
            yield from self.publish_tasks()
            yield from self.bundle_sizes_task()
        yield from self.prune_task()

    def copy_tasks(self):
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
                yield copy_task(resource.path, resource.source, target)
        if not self.mode.production:
            for resource in self.media:
                if not resource.text:
                    yield copy_task(
                        resource.path, resource.source, self.out / resource.path
                    )

    def media_tasks(self):
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
                file_dep += CODE + templates.page_layouts(resource)
            yield {
                "basename": "image" if resource.kind == "svg" else "media",
                "name": path,
                "actions": [(render.media, [self.site, resource])],
                "file_dep": sorted(set(file_dep)),
                "targets": [str(self.site.generated[path])],
                "uptodate": [self.uptodate, environment("node", "esbuild", "ttx")],
            }

    def image_tasks(self):
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

    def cover_tasks(self):
        for resource in self.pages:
            if resource.kind != "html":
                continue
            target = self.site.generated[resource.cover_image()]
            cover = resource.meta.get("cover")
            file_dep = COVER_DEPS + [str(FAVICON)]
            if cover:
                # Generated images are used as is. For SVG, the source is used
                # to keep the original fonts.
                image = self.site.resources.get(f"media/images/{cover}")
                if image is None:
                    raise ValueError(f"{resource}: unknown cover {cover}")
                cover = (
                    self.site.raw(f"images/{cover}") if image.python else image.source
                )
                file_dep.append(str(cover))
            title, author = resource.meta.title, resource.meta.author
            yield {
                "basename": "cover",
                "name": resource.path,
                "actions": [(covers.generate, [title, author, cover, target])],
                "file_dep": file_dep,
                "targets": [str(target)],
                "uptodate": [
                    environment(
                        variables=("FONTCONFIG_FILE",),
                        title=title,
                        author=author,
                    )
                ],
            }

    def fragment_tasks(self):
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
                + CODE
                + templates.article_layouts(resource)
                + [
                    str(self.site.generated[thumb])
                    for thumb in self.gallery_thumbs.get(path, [])
                ],
                "targets": [str(target)],
                "task_dep": [] if post else ["article"],
                "uptodate": [self.uptodate, environment("node")],
            }

    def page_tasks(self):
        for resource in self.pages:
            target = self.out / resource.path
            fragment = self.fragments.get(resource.path)
            file_dep = [str(resource.source)] + CODE + PAGE_CSS_DEPS
            file_dep += templates.page_layouts(resource)
            if fragment:
                file_dep.append(str(fragment))
            task_dep = ["article", "image"]
            if self.mode.production:
                task_dep += ["font", "asset"]
                if resource.kind == "html":
                    task_dep.append(f"cover:{resource.path}")
            yield {
                "basename": "page",
                "name": resource.path,
                "actions": [(render.page, [self.site, resource, fragment, target])],
                "file_dep": file_dep,
                "targets": [str(target)],
                "task_dep": task_dep,
                "uptodate": [self.uptodate, environment("node", "ffprobe")],
            }

    def pagefind_tasks(self):
        target = self.site.generated["js/pagefind.js"]
        yield {
            "basename": "pagefind-js",
            "doc": "extract the pagefind library",
            "actions": [(pagefind.extract, [target])],
            "targets": [str(target)],
            "uptodate": [environment("pagefind")],
        }
        pages = [str(self.out / r.path) for r in self.pages if r.kind == "html"]
        yield {
            "basename": "pagefind",
            "doc": "build search index",
            "actions": [(pagefind.index, [self.site])],
            "file_dep": pages,
            "task_dep": ["prune"],
            "targets": [str(self.mode.cache / "pagefind.json")],
            "uptodate": [(pagefind.exist, [self.site]), environment("pagefind")],
        }

    def font_tasks(self):
        fragments = list(self.fragments.values())
        yield {
            "basename": "glyphs",
            "doc": "collect glyphs used in articles",
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
                "uptodate": [environment("pyftsubset")],
            }

    def publish_tasks(self):
        """Media files get a name with a hash of their content."""
        tools = environment(
            "svgo",
            "jpgicc",
            "avifenc",
            "cjpegli",
            "pngquant",
            "cwebp",
            "gif2webp",
            "gifsicle",
            "exiftool",
            variables=("SRGB_PROFILE",),
        )
        for path in self.published:
            sidecar = self.site.sidecar(path)
            file_dep = [str(self.site.raw(path))]
            task_dep = []
            uptodate = [(publish.exist, [self.site, sidecar])]
            if path.startswith("images/"):
                basename = "optimize"
                action = publish.image
                file_dep += OPTIMIZE_DEPS
                uptodate.append(tools)
            elif path.startswith("fonts/"):
                basename = "font"
                action = publish.file
            elif path.startswith("css/"):
                basename = "asset"
                action = publish.css
                task_dep = ["image", "font"]
                uptodate.append(self.uptodate)
            else:
                basename = "asset"
                action = publish.file
            yield {
                "basename": basename,
                "name": path,
                "actions": [(action, [self.site, path, sidecar])],
                "file_dep": file_dep,
                "targets": [str(sidecar)],
                "task_dep": task_dep,
                "uptodate": uptodate,
            }

    def bundle_sizes_task(self):
        target = self.out / "bundle-sizes.txt"
        pages = [str(self.out / r.path) for r in self.pages if r.kind == "html"]
        bundles = [
            path
            for path in self.published
            if path.count("/") == 1
            and path.endswith((".css", ".js", ".woff2"))
            and path.startswith(("css/", "js/", "fonts/"))
        ]
        yield {
            "basename": "bundle-sizes",
            "doc": "report sizes of stylesheets, scripts and fonts",
            "actions": [(publish.bundle_sizes, [self.site, bundles, target])],
            "file_dep": pages + [str(self.site.sidecar(b)) for b in bundles],
            "targets": [str(target)],
            "uptodate": [environment("gzip", "brotli")],
        }

    def prune_task(self):
        kinds = ["pagefind-js"] + [
            kind
            for kind, (_, production) in GROUPS.items()
            if self.mode.production or not production
        ]
        if self.mode.production:
            kinds += ["glyphs", "bundle-sizes"]
        yield {
            "basename": "prune",
            "doc": "remove obsolete files",
            "actions": [(files.prune, [self])],
            "task_dep": kinds,
            "uptodate": [False],
        }

    def expected(self):
        """Files expected in the output directory."""
        result = {self.out / r.path for r in self.copies + self.pages}
        if self.mode.production:
            result.add(self.out / "bundle-sizes.txt")
            for path in self.published:
                try:
                    with open(self.site.sidecar(path)) as f:
                        names = json.load(f)["files"]
                except FileNotFoundError:
                    continue
                result.update(self.out / "media" / f for f in names)
        else:
            result.update(self.out / r.path for r in self.media)
            result.update(self.site.generated.values())
        return {str(p) for p in result}


def copy_task(name, source, target):
    return {
        "basename": "copy",
        "name": name,
        "actions": [(files.copy, [source, target])],
        "file_dep": [str(source)],
        "targets": [str(target)],
    }
